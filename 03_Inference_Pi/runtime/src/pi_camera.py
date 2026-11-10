import os, sys, subprocess, threading, time
from pathlib import Path
from collections import deque
import cv2
import numpy as np
PACKAGE=Path(__file__).resolve().parents[1]

class PiCamera:
    """Continuously drain frames so CPU inference does not accumulate old images."""
    def __init__(self,index,width=1280,height=720,profile_path=None):
        self.index=index
        self.profile_path=Path(profile_path) if profile_path else PACKAGE/'config/camera_profile.json'
        self.settings_process=None
        backend=cv2.CAP_DSHOW if __import__('os').name=='nt' else cv2.CAP_V4L2
        self.cap=cv2.VideoCapture(index,backend)
        if not self.cap.isOpened():
            self.cap.release();self.cap=cv2.VideoCapture(index)
        if not self.cap.isOpened():raise RuntimeError('Cannot open camera; close other camera applications')
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,height)
        self.buffer_requested=self.cap.set(cv2.CAP_PROP_BUFFERSIZE,1) if os.name!="nt" else False
        self.buffer_size=self.cap.get(cv2.CAP_PROP_BUFFERSIZE)
        # Only apply a profile explicitly saved in the camera panel, for the same device.
        if os.name!='nt':
            try:
                from camera_controls import apply_saved_profile
                if apply_saved_profile(f'/dev/video{index}',self.profile_path):
                    print('Saved camera profile applied and verified.',flush=True)
            except Exception as error:
                self.cap.release()
                raise RuntimeError('Saved camera profile could not be applied: '+str(error)+
                    '. Open src/camera_controls.py to inspect/save a new profile.') from error
        self.lock=threading.Lock();self.io_lock=threading.Lock();self.paused=threading.Event()
        self.latest=None;self.stamp=0.;self.stop=threading.Event()
        self.frame_times=deque(maxlen=120);self.read_times=deque(maxlen=120)
        self.thread=threading.Thread(target=self._read,daemon=True);self.thread.start()

    def _read(self):
        try:
            while not self.stop.is_set():
                if self.paused.is_set():
                    self.stop.wait(.01);continue
                start=time.monotonic()
                # Never hold the published-frame lock during blocking camera I/O.
                with self.io_lock:ok,frame=self.cap.read()
                end=time.monotonic()
                if ok:
                    with self.lock:
                        self.latest=frame;self.stamp=end
                        self.frame_times.append(end);self.read_times.append((end-start)*1000)
                else:self.stop.wait(.05)
                self.stop.wait(.001)
        finally:self.cap.release()

    def read(self,copy_frame=True):
        with self.lock:
            frame,stamp=self.latest,self.stamp
        return (None if frame is None else frame.copy() if copy_frame else frame),stamp

    def metrics(self):
        with self.lock:
            stamps=list(self.frame_times);times=list(self.read_times)
        return {'camera_buffer_size':self.buffer_size,'camera_buffer_request_accepted':self.buffer_requested,'camera_fps':(len(stamps)-1)/(stamps[-1]-stamps[0]) if len(stamps)>1 else 0.,
                'camera_read_ms_median':float(np.median(times)) if times else None}

    def settings(self):
        if os.name!='nt':
            if self.settings_process is not None and self.settings_process.poll() is None:return
            script=Path(__file__).with_name('camera_controls.py')
            self.settings_process=subprocess.Popen([sys.executable,str(script),'--device',f'/dev/video{self.index}',
                '--no-preview','--profile',str(self.profile_path)])
            return
        self.paused.set()
        try:
            with self.io_lock:
                if int(self.cap.get(cv2.CAP_PROP_BACKEND))==cv2.CAP_DSHOW:
                    self.cap.set(cv2.CAP_PROP_SETTINGS,0)
                else:print('Camera controls require the native camera utility on this platform.',flush=True)
        finally:self.paused.clear()

    def close(self):
        self.stop.set();self.thread.join(timeout=2)

