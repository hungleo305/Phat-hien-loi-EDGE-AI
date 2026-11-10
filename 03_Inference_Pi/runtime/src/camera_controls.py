"""USB-camera control panel for Linux. Uses V4L2 controls reported by the driver.

Opening the panel never changes camera settings. No Torch/model imports required.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time


@dataclass
class Control:
    name: str
    kind: str
    minimum: int = 0
    maximum: int = 1
    step: int = 1
    default: int | None = None
    value: int = 0
    flags: str = ''
    menu: dict = field(default_factory=dict)

    @property
    def writable(self):
        return self.kind in ('int','int64','bool','menu','intmenu') and not any(
            flag in self.flags for flag in ('read-only','write-only','disabled'))

    @property
    def active(self):
        return self.writable and 'inactive' not in self.flags and 'grabbed' not in self.flags

    def validate(self, value):
        value=int(value)
        if self.kind in ('menu','intmenu') and value not in self.menu:
            raise ValueError(f'{self.name}: unsupported menu value {value}')
        if not self.minimum<=value<=self.maximum or (value-self.minimum)%max(1,self.step):
            raise ValueError(f'{self.name}: use {self.minimum}..{self.maximum}, step {self.step}')
        return value


def parse_controls(text):
    controls={};current=None
    for line in text.splitlines():
        match=re.match(r'^\s*(\w+)\s+0x[0-9a-fA-F]+\s+\(([^)]+)\)\s*:\s*(.*)$',line)
        if match:
            name,kind,tail=match.groups()
            props={k:int(v) for k,v in re.findall(r'\b(min|max|step|default|value)=(-?\d+)',tail)}
            if 'value' not in props:current=None;continue
            current=Control(name,kind,props.get('min',0),props.get('max',1),
                props.get('step',1),props.get('default'),props['value'],tail.split('flags=',1)[-1] if 'flags=' in tail else '')
            controls[name]=current
        elif current is not None and current.kind in ('menu','intmenu'):
            item=re.match(r'^\s+(-?\d+):\s*(.*)$',line)
            if item:current.menu[int(item[1])]=item[2].strip()
    return controls


class V4L2Camera:
    def __init__(self, device='/dev/video0', runner=None):
        if not re.fullmatch(r'/dev/video\d+',str(device)):
            raise ValueError('Expected a video device such as /dev/video0')
        self.device=str(device)
        self.tool=shutil.which('v4l2-ctl') or 'v4l2-ctl'
        self.runner=runner or subprocess.run

    def run(self,*args):
        result=self.runner([self.tool,'-d',self.device,*args],capture_output=True,text=True,timeout=4)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or f'v4l2-ctl exit {result.returncode}').strip())
        return result.stdout

    def controls(self):
        controls=parse_controls(self.run('--list-ctrls-menus'))
        if not controls:raise RuntimeError('No supported camera controls returned by the driver')
        return controls

    def identity(self):
        text=self.run('--info')
        result={}
        for key,label in [('driver','Driver name'),('card','Card type'),('bus','Bus info')]:
            match=re.search(r'^\s*'+label+r'\s*:\s*(.+)$',text,re.M)
            if match:result[key]=match[1].strip()
        if not all(result.get(k) for k in ('driver','card','bus')):
            raise RuntimeError('Cannot identify camera driver/card/USB bus; profile not saved or applied')
        return result

    def set_one(self,name,value):
        control=self.controls().get(name)
        if control is None or not control.active:
            raise ValueError(f'{name}: unavailable/inactive; change Auto/Manual mode first')
        value=control.validate(value)
        self.run(f'--set-ctrl={name}={value}')

    def apply(self, values):
        """Order automatic selectors before dependent controls; verify readback."""
        controls=self.controls()
        for name,value in values.items():
            if name not in controls or not controls[name].writable:
                raise ValueError(f'Unsupported control: {name}')
            controls[name].validate(value)
        # Temporarily enable manual controls only when the operation includes them.
        selectors={}
        if any(n in values for n in ('exposure_time_absolute','exposure_absolute')):
            for n in ('auto_exposure','exposure_auto'):
                if n in controls and 1 in controls[n].menu:selectors[n]=1
        if 'white_balance_temperature' in values:
            for n in ('white_balance_temperature_auto','white_balance_automatic'):
                if n in controls:selectors[n]=0
        if 'gain' in values:
            for n in ('autogain','auto_gain'):
                if n in controls:selectors[n]=0
        # Preserve selectors unless the user explicitly requested another mode.
        final_selectors={name:int(values.get(name,controls[name].value)) for name in selectors}
        try:
            for name,value in selectors.items():self.set_one(name,value)
            auto_names={'auto_exposure','exposure_auto','white_balance_temperature_auto',
                'white_balance_automatic','autogain','auto_gain','focus_auto','focus_automatic_continuous'}
            for name,value in values.items():
                if name not in auto_names:self.set_one(name,value)
            for name,value in values.items():
                if name in auto_names:self.set_one(name,value)
        finally:
            # Even a failed dependent setting must not silently leave an auto mode disabled.
            for name,value in final_selectors.items():self.set_one(name,value)
        actual=self.controls()
        mismatches=[]
        for name,value in values.items():
            if actual[name].active and actual[name].value!=int(value):
                mismatches.append(f'{name}: requested {value}, driver returned {actual[name].value}')
        if mismatches:raise RuntimeError('; '.join(mismatches))
        return actual

    def save_profile(self,path):
        controls=self.controls()
        profile={'schema':1,'camera':self.identity(),'device_when_saved':self.device,
            'saved_at':datetime.now().astimezone().isoformat(),'apply_on_startup':True,
            'values':{name:c.value for name,c in controls.items() if c.active}}
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.json.pending')
        temporary.write_text(json.dumps(profile,indent=2),encoding='utf-8')
        temporary.replace(path)
        return profile

    def load_profile(self,path):
        profile=json.loads(Path(path).read_text(encoding='utf-8'))
        if profile.get('schema')!=1 or profile.get('camera')!=self.identity():
            raise ValueError('Profile belongs to another camera/USB port; read controls and save a new profile')
        values=profile.get('values')
        if not isinstance(values,dict) or not values:raise ValueError('Empty/invalid camera profile')
        return self.apply(values)


def apply_saved_profile(device, path):
    path=Path(path)
    if not path.is_file():return False
    profile=json.loads(path.read_text(encoding='utf-8'))
    if not profile.get('apply_on_startup'):return False
    V4L2Camera(device).load_profile(path)
    return True


class CameraFeed:
    """Capture thread; blocking USB reads never block Tk controls."""
    def __init__(self,index):
        self.index=index;self.frame=None;self.stamp=0.;self.error='Opening camera...'
        self.lock=threading.Lock();self.stop=threading.Event()
        threading.Thread(target=self._run,daemon=True).start()

    def _run(self):
        import cv2
        cap=cv2.VideoCapture(self.index,cv2.CAP_V4L2)
        try:
            if not cap.isOpened():
                self.error='Cannot open camera. Close other camera applications or use --no-preview.'
                return
            while not self.stop.is_set():
                ok,frame=cap.read()
                if ok:
                    with self.lock:self.frame=frame;self.stamp=time.monotonic();self.error=''
                else:self.stop.wait(.05)
        finally:cap.release()

    def read(self):
        with self.lock:return self.frame,self.stamp,self.error


class ControlPanel:
    def __init__(self,root,camera,profile,no_preview=False,feed=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk=tk;self.ttk=ttk;self.root=root;self.camera=camera;self.profile=Path(profile)
        self.executor=ThreadPoolExecutor(max_workers=1);self.jobs=[];self.pending={}
        self.rows={};self.original=None;self.controls={};self.closed=False;self.photo=None
        self.timer=None;self.version=0;self.busy=False
        root.title('USB Camera Properties - Raspberry Pi')
        root.geometry('1120x680');root.minsize(850,560)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.status=tk.StringVar(value='Reading camera controls... Opening does not change settings.')
        self.live_apply=tk.BooleanVar(value=True)
        self.status_label=ttk.Label(root,textvariable=self.status,wraplength=1080)
        self.status_label.pack(side='bottom',fill='x',padx=12,pady=10)
        buttons=ttk.Frame(root);buttons.pack(side='bottom',fill='x',padx=10,pady=6)
        for label,command in [('Auto exposure / recover',self.recover_auto),('Defaults',self.defaults),
            ('Windows colors',self.windows_colors),
            ('Undo session',self.undo),('Read camera',self.refresh),('Apply',self.flush),
            ('Save + use on startup',self.save),('Load saved',self.load),('Close',self.close)]:
            ttk.Button(buttons,text=label,command=command).pack(side='left',padx=2)
        main=ttk.Frame(root);main.pack(fill='both',expand=True,padx=10,pady=5)
        left=ttk.Frame(main);left.pack(side='left',fill='both',expand=True)
        ttk.Label(left,text=f'{camera.device} — controls reported by the camera driver').pack(anchor='w')
        ttk.Checkbutton(left,text='Apply adjustments automatically',variable=self.live_apply).pack(anchor='w',pady=5)
        self.notebook=ttk.Notebook(left);self.notebook.pack(fill='both',expand=True)
        self.tabs={}
        for name in ('Video Proc Amp','Camera Control'):
            tab=ttk.Frame(self.notebook,padding=8);self.notebook.add(tab,text=name);self.tabs[name]=tab
        right=ttk.Frame(main,width=390);right.pack(side='right',fill='both',padx=(12,0))
        ttk.Label(right,text='Live camera preview',font=('',12,'bold')).pack(anchor='w')
        self.image_label=ttk.Label(right,text='Model preview remains open in its own window.' if no_preview else 'Opening USB camera...',anchor='center')
        self.image_label.pack(fill='both',expand=True)
        self.image_status=tk.StringVar(value='')
        ttk.Label(right,textvariable=self.image_status,wraplength=390).pack(fill='x',pady=6)
        ttk.Label(right,text='Exposure slider uses a logarithmic scale.\nNumeric box accepts driver units.\nLong exposure may reduce camera frame rate.\n\nOpening this panel changes nothing.\nDefaults / Auto can recover a dark image.\nSave stores actual driver values for startup.',wraplength=390).pack(anchor='w',pady=8)
        self.feed=feed if feed is not None else (None if no_preview else CameraFeed(int(camera.device.removeprefix('/dev/video'))))
        self.submit(self.camera.controls,self.got_controls)
        self.root.after(50,self.poll)
        self.root.after(60,self.draw_frame)

    def submit(self,function,callback=None):
        if self.closed:return
        self.jobs.append((self.executor.submit(function),callback))

    def poll(self):
        if self.closed:return
        current,self.jobs=self.jobs,[]
        for future,callback in current:
            if not future.done():self.jobs.append((future,callback));continue
            try:
                result=future.result()
                if callback:callback(result)
            except Exception as error:
                self.busy=False;self.status.set('ERROR: '+str(error))
        self.root.after(60,self.poll)

    def got_controls(self,controls):
        self.controls=controls
        if self.original is None:self.original={n:c.value for n,c in controls.items() if c.active}
        if not self.rows:
            for control in controls.values():self.make_row(control)
        for name,control in controls.items():
            row=self.rows.get(name)
            if row is None:continue
            if name not in self.pending:self.update_row(control)
        self.status.set('Camera values read back. Changes are applied only by controls/buttons.')

    def make_row(self,control):
        tk,ttk=self.tk,self.ttk
        camera_names=('exposure','focus','zoom','iris','pan','tilt')
        tab=self.tabs['Camera Control' if any(k in control.name for k in camera_names) else 'Video Proc Amp']
        rownum=len(tab.grid_slaves(column=0))
        ttk.Label(tab,text=control.name.replace('_',' ').title(),width=26).grid(row=rownum,column=0,sticky='w',pady=5)
        var=tk.StringVar(value=str(control.value));widgets=[]
        if control.kind in ('menu','intmenu'):
            choices=[f'{k}: {v}' for k,v in control.menu.items()]
            widget=ttk.Combobox(tab,values=choices,state='readonly',width=32)
            widget.grid(row=rownum,column=1,columnspan=2,sticky='ew')
            widget.bind('<<ComboboxSelected>>',lambda event,n=control.name,w=widget:self.stage(n,int(w.get().split(':',1)[0])))
            widgets.append(widget);scale=None
        elif control.kind=='bool':
            widget=ttk.Checkbutton(tab,variable=var,onvalue='1',offvalue='0',command=lambda n=control.name,v=var:self.stage(n,int(v.get())))
            widget.grid(row=rownum,column=1,sticky='w');widgets.append(widget);scale=None
        elif control.kind in ('int','int64'):
            scale=ttk.Scale(tab,from_=0,to=1000,command=lambda value,n=control.name:self.slide(n,value))
            scale.grid(row=rownum,column=1,sticky='ew',padx=4)
            spin=ttk.Spinbox(tab,from_=control.minimum,to=control.maximum,increment=max(1,control.step),textvariable=var,width=9,
                command=lambda n=control.name,v=var:self.entry(n,v))
            spin.grid(row=rownum,column=2,padx=3)
            spin.bind('<Return>',lambda event,n=control.name,v=var:self.entry(n,v))
            spin.bind('<FocusOut>',lambda event,n=control.name,v=var:self.entry(n,v))
            widgets.extend([scale,spin]);widget=spin
        else:
            widget=ttk.Label(tab,text=f'{control.kind}: {control.value} (not editable)');widget.grid(row=rownum,column=1);scale=None
        note=ttk.Label(tab,text='',width=27);note.grid(row=rownum,column=3,padx=4,sticky='w')
        tab.columnconfigure(1,weight=1)
        self.rows[control.name]={'var':var,'widgets':widgets,'widget':widget,'scale':scale,'note':note,'updating':False}
        self.update_row(control)

    @staticmethod
    def position(control,value):
        if control.maximum<=control.minimum:return 0.
        if 'exposure' in control.name and control.minimum>0:
            return 1000*math.log(max(control.minimum,value)/control.minimum)/math.log(control.maximum/control.minimum)
        return 1000*(value-control.minimum)/(control.maximum-control.minimum)

    @staticmethod
    def value_at(control,position):
        fraction=max(0.,min(1.,float(position)/1000))
        if 'exposure' in control.name and control.minimum>0:
            raw=control.minimum*(control.maximum/control.minimum)**fraction
        else:raw=control.minimum+(control.maximum-control.minimum)*fraction
        value=control.minimum+round((raw-control.minimum)/max(1,control.step))*max(1,control.step)
        return min(control.maximum,max(control.minimum,value))

    def update_row(self,control):
        row=self.rows[control.name];row['updating']=True
        try:
            row['var'].set(str(control.value))
            if control.kind in ('menu','intmenu'):
                row['widget'].set(f'{control.value}: {control.menu.get(control.value,"Unknown")}')
            elif row['scale'] is not None:row['scale'].set(self.position(control,control.value))
            for widget in row['widgets']:
                widget.configure(state=('readonly' if control.kind in ('menu','intmenu') else 'normal') if control.active else 'disabled')
            row['note'].configure(text='inactive (Auto mode)' if 'inactive' in control.flags else
                'read only' if not control.writable else f'default {control.default} | step {control.step}')
        finally:row['updating']=False

    def slide(self,name,position):
        row=self.rows.get(name)
        if row is None or row['updating']:return
        value=self.value_at(self.controls[name],position)
        row['var'].set(str(value));self.stage(name,value)

    def entry(self,name,var):
        row=self.rows.get(name)
        if row is None or row['updating']:return
        try:
            value=self.controls[name].validate(var.get())
            if value!=self.controls[name].value:self.stage(name,value)
        except ValueError as error:self.status.set(str(error))

    def stage(self,name,value):
        if not self.controls[name].active:return
        try:self.controls[name].validate(value)
        except ValueError as error:self.status.set(str(error));return
        self.pending[name]=value
        self.status.set(f'Pending: {name}={value}')
        if self.timer:self.root.after_cancel(self.timer)
        self.timer=self.root.after(250,self.flush) if self.live_apply.get() else None

    def flush(self,after=None):
        self.timer=None
        if self.busy:
            self.timer=self.root.after(150,lambda:self.flush(after));return
        if not self.pending:
            if after:after()
            return
        values=dict(self.pending);self.pending.clear();self.busy=True
        self.status.set('Applying camera controls...')
        def done(controls):
            self.busy=False;self.got_controls(controls)
            if self.pending:self.flush(after)
            elif after:after()
        self.submit(lambda:self.camera.apply(values),done)

    def action(self,function,done=None):
        self.pending.clear()
        if self.timer:self.root.after_cancel(self.timer);self.timer=None
        self.submit(function,done or self.got_controls)

    def refresh(self):self.action(self.camera.controls)

    def recover_auto(self):
        def operation():
            controls=self.camera.controls()
            for name in ('auto_exposure','exposure_auto'):
                if name in controls:
                    menu=controls[name].menu
                    candidates=[k for k,label in menu.items() if 'aperture priority' in label.lower() or label.lower() in ('auto mode','auto')]
                    if candidates:return self.camera.apply({name:candidates[0]})
            raise ValueError('Camera does not report a supported automatic exposure mode')
        self.action(operation)

    def defaults(self):
        def operation():
            controls=self.camera.controls()
            return self.camera.apply({n:c.default for n,c in controls.items() if c.writable and c.default is not None})
        self.action(operation)

    def windows_colors(self):
        # Values transcribed from the user's Windows properties screenshot.
        # No exposure value was shown there; do not invent or change it.
        reference={'brightness':-24,'contrast':238,'saturation':303,'sharpness':125,
            'gamma':20,'white_balance_temperature':4500,'backlight_compensation':0,'gain':5}
        def operation():
            controls=self.camera.controls()
            values={n:v for n,v in reference.items() if n in controls and controls[n].active}
            if not values:raise ValueError('No matching active controls for Windows reference')
            return self.camera.apply(values)
        self.action(operation)

    def undo(self):
        if self.original:self.action(lambda:self.camera.apply(self.original))

    def save(self):
        def operation():
            profile=self.camera.save_profile(self.profile)
            return profile
        def done(profile):self.status.set(f'Saved actual camera values: {self.profile}. They will be applied on preview startup.')
        self.flush(lambda:self.submit(operation,done))

    def load(self):self.action(lambda:self.camera.load_profile(self.profile))

    def draw_frame(self):
        if self.closed:return
        if self.feed is not None:
            frame,stamp,error=self.feed.read()
            if frame is not None:
                import cv2
                h,w=frame.shape[:2];width=380;height=max(1,round(h*width/w))
                rgb=cv2.cvtColor(cv2.resize(frame,(width,height)),cv2.COLOR_BGR2RGB)
                self.photo=self.tk.PhotoImage(data=f'P6\n{width} {height}\n255\n'.encode()+rgb.tobytes(),format='PPM')
                self.image_label.configure(image=self.photo,text='')
                mean=float(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY).mean())
                age=time.monotonic()-stamp
                self.image_status.set(f'{w}x{h} | frame age {age:.1f}s | gray mean {mean:.1f}'+
                    ('\nDark image: try Auto exposure / Defaults.' if mean<25 else '')+
                    ('\nFrame delayed; long exposure may slow capture.' if age>1 else ''))
            else:self.image_status.set(error)
        self.root.after(80,self.draw_frame)

    def close(self):
        self.closed=True
        if self.feed is not None:self.feed.stop.set()
        self.executor.shutdown(wait=False,cancel_futures=True)
        self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',default='/dev/video0')
    parser.add_argument('--no-preview',action='store_true',help='Use existing model camera window; do not reopen camera')
    parser.add_argument('--profile',type=Path,default=Path(__file__).resolve().parents[1]/'runs/camera_profile.json')
    parser.add_argument('--apply-profile',action='store_true',help='Apply a saved profile without a desktop')
    args=parser.parse_args()
    if shutil.which('v4l2-ctl') is None:parser.error('v4l2-ctl is required: sudo apt install v4l-utils')
    camera=V4L2Camera(args.device)
    if args.apply_profile:
        camera.load_profile(args.profile);print('Camera profile applied and read back.');return
    try:
        import tkinter as tk
        root=tk.Tk()
    except ImportError:
        parser.error('Tk is required: sudo apt install python3-tk. Keep the existing .venv.')
    except Exception as error:
        parser.error('Open this panel in the Pi desktop terminal (HDMI or Remote Desktop): '+str(error))
    ControlPanel(root,camera,args.profile,args.no_preview)
    root.mainloop()


if __name__=='__main__':main()
