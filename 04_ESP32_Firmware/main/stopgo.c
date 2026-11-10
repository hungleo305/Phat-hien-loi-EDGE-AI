#include "stopgo.h"
#include <string.h>
#include <limits.h>

/* Transport measures motor-on time. The active servo out/return cycle measures
   wall time: the servo can push even while the camera briefly stops the belt. */
static void advance_clock(stopgo_t *s, uint64_t now) {
    if (now>=s->last_clock_ms && s->motor_running)
        s->motor_ms+=now-s->last_clock_ms;
    s->last_clock_ms=now;
}

static sg_box_t *head_box(stopgo_t *s) {
    return s->count ? &s->boxes[s->head] : NULL;
}
static sg_box_t *find_box(stopgo_t *s, uint32_t id) {
    for (unsigned i=0; i<s->count; ++i) {
        sg_box_t *box=&s->boxes[(s->head+i)%SG_QUEUE_CAPACITY];
        if (box->id==id) return box;
    }
    return NULL;
}
static unsigned motor_sync(stopgo_t *s) {
    bool run=s->state==SG_FEEDING && s->gate_phase!=SG_GATE_WAIT_RESULT;
    if (run==s->motor_running) return 0;
    s->motor_running=run;
    return run ? SG_MOTOR_ON : SG_MOTOR_OFF;
}
static unsigned fail(stopgo_t *s, const char *reason) {
    s->state=SG_FAULT;
    s->fault=reason;
    s->motor_running=false;
    /* A box may still lean on the diverter. Retracting on a fault can change
       its route or wedge it. Stop transport and keep the commanded position;
       the operator clears the belt before reset/m0 returns the arm home. */
    return SG_MOTOR_OFF|SG_ALARM;
}
static unsigned route_head(stopgo_t *s, uint64_t now) {
    sg_box_t *box=head_box(s);
    if (!box || !box->result_ready) return fail(s,"GATE_WITHOUT_RESULT");
    s->defect=box->defect;
    s->phase_ms=now;
    s->phase_motor_ms=s->motor_ms;
    if (box->defect && s->sorting_enabled) {
        s->gate_phase=SG_GATE_SWEEP_OUT;
        /* IR owns this exact FIFO head. Actively sweep it now; do not stop
           the conveyor just to sort and do not hold a passive rail for 3 s. */
        return SG_ROUTED|SG_REJECT|motor_sync(s);
    }
    s->gate_phase=SG_GATE_PASSING;
    return SG_ROUTED|motor_sync(s);
}
static unsigned finish_head(stopgo_t *s) {
    sg_box_t *box=head_box(s);
    if (!box) return fail(s,"GATE_QUEUE_EMPTY");
    s->finished_id=box->id;
    s->head=(s->head+1)%SG_QUEUE_CAPACITY;s->count--;
    s->gate_phase=SG_GATE_IDLE;s->gate_released=false;
    return SG_FINISHED|motor_sync(s);
}
void sg_init(stopgo_t *s, uint32_t session, sg_config_t config) {
    memset(s,0,sizeof(*s));
    s->session=session;s->config=config;s->state=SG_STOPPED;
    s->gate_phase=SG_GATE_IDLE;
}
unsigned sg_start(stopgo_t *s, uint64_t now, bool camera, bool gate) {
    advance_clock(s,now);
    if (s->state!=SG_STOPPED || !s->pi_ready || camera || gate || s->count || s->servo_moving) return 0;
    s->state=SG_FEEDING;s->since_ms=now;
    s->previous_camera=s->previous_gate=false;
    return motor_sync(s);
}
unsigned sg_stop(stopgo_t *s) {
    if (s->state==SG_STOPPED) return SG_MOTOR_OFF|SG_SERVO_HOME;
    if (s->state==SG_JOG) {
        s->state=SG_STOPPED;s->motor_running=false;
        return SG_MOTOR_OFF|SG_JOG_DONE;
    }
    /* m0 is an intentional operator stop, not a machine failure.  Cancel all
       in-flight tracking because the operator may remove/reposition boxes
       while stopped.  m1 still requires READY and both sensors clear. */
    s->state=SG_STOPPED;s->gate_phase=SG_GATE_IDLE;s->fault=NULL;
    s->motor_running=s->result_ready=s->defect=s->gate_released=false;
    s->previous_camera=s->previous_gate=false;
    s->count=s->head=0;s->capture_id=s->result_id=s->finished_id=0;
    return SG_MOTOR_OFF|SG_SERVO_HOME;
}
unsigned sg_jog(stopgo_t *s, uint64_t now, uint32_t duration_ms, bool camera, bool gate) {
    advance_clock(s,now);
    if (s->state!=SG_STOPPED || s->sorting_enabled || s->count ||
        camera || gate || !duration_ms || duration_ms>SG_JOG_MAX_MS) return 0;
    s->state=SG_JOG;s->since_ms=now;s->jog_ms=duration_ms;s->motor_running=true;
    return SG_MOTOR_ON;
}
bool sg_reset(stopgo_t *s, bool camera, bool gate) {
    if ((s->state!=SG_FAULT && s->state!=SG_STOPPED) || camera || gate) return false;
    s->state=SG_STOPPED;s->gate_phase=SG_GATE_IDLE;s->fault=NULL;
    s->result_ready=s->defect=s->previous_camera=s->previous_gate=s->motor_running=s->gate_released=false;
    s->count=s->head=0;s->capture_id=s->result_id=s->finished_id=0;
    return true; /* Operator must remove every box; IDs stay monotonic. */
}
unsigned sg_captured(stopgo_t *s, uint64_t now, uint32_t session, uint32_t id) {
    advance_clock(s,now);
    if (s->state!=SG_WAIT_CAPTURE || session!=s->session || id!=s->capture_id) return 0;
    sg_box_t *box=find_box(s,id);
    if (!box || box->captured) return 0;
    if (now-s->since_ms>=s->config.capture_timeout_ms) return fail(s,"PI_CAPTURE_TIMEOUT");
    box->captured=true;box->captured_ms=now;
    box->captured_motor_ms=s->motor_ms;
    s->captured_ms=now;s->state=SG_FEEDING;
    return SG_IMAGE_ACCEPTED|motor_sync(s);
}
unsigned sg_result(stopgo_t *s, uint64_t now, uint32_t session, uint32_t id, sg_result_t result) {
    advance_clock(s,now);
    if (session!=s->session || s->state==SG_FAULT || s->state==SG_STOPPED ||
        s->state==SG_JOG) return 0;
    sg_box_t *box=find_box(s,id);
    if (!box || box->result_ready) return 0;
    if (result==SG_ERROR) return fail(s,box->captured?"PI_INSPECTION_ERROR":"PI_CAPTURE_ERROR");
    if (!box->captured) return 0; /* An image ACK is mandatory. */
    if (now-box->captured_ms>=s->config.result_timeout_ms) return fail(s,"PI_RESULT_TIMEOUT");
    box->result_ready=true;box->defect=result==SG_DEFECT;
    s->result_id=id;s->result_ready=true;s->defect=box->defect;
    unsigned actions=SG_ACCEPTED;
    if (s->gate_phase==SG_GATE_WAIT_RESULT && head_box(s)==box)
        actions|=route_head(s,now);
    return actions;
}
unsigned sg_tick(stopgo_t *s, uint64_t now, bool camera, bool gate) {
    advance_clock(s,now);
    bool camera_rise=camera && !s->previous_camera;
    bool gate_rise=gate && !s->previous_gate;
    bool gate_fall=!gate && s->previous_gate;
    s->previous_camera=camera;s->previous_gate=gate;
    if (s->state==SG_JOG) {
        if (camera || gate || now-s->since_ms>=s->jog_ms) {
            s->state=SG_STOPPED;s->motor_running=false;
            return SG_MOTOR_OFF|SG_JOG_DONE;
        }
        return 0;
    }
    if (s->state==SG_STOPPED || s->state==SG_FAULT) return 0;
    for (unsigned i=0; i<s->count; ++i) {
        sg_box_t *box=&s->boxes[(s->head+i)%SG_QUEUE_CAPACITY];
        if (!box->captured) continue;
        if (!box->result_ready && now-box->captured_ms>=s->config.result_timeout_ms)
            return fail(s,"PI_RESULT_TIMEOUT");
        if (s->motor_ms-box->captured_motor_ms>=s->config.gate_timeout_ms)
            return fail(s,"GATE_TRANSIT_TIMEOUT");
    }
    unsigned actions=0;
    /* Complete due servo phases before accepting a new IR edge. Otherwise an
       edge on the exact return deadline could spuriously report busy. */
    if (s->gate_phase==SG_GATE_SWEEP_OUT && !s->servo_moving && now-s->phase_ms>=s->config.reject_ms) {
        s->gate_phase=SG_GATE_SWEEP_RETURN;s->phase_ms=now;
        actions|=SG_SERVO_HOME;
    } else if (s->gate_phase==SG_GATE_SWEEP_RETURN && !s->servo_moving &&
               now-s->phase_ms>=s->config.servo_return_ms) {
        s->gate_phase=SG_GATE_WAIT_CLEAR;
        if (s->gate_released) actions|=finish_head(s);
    }
    if (s->state==SG_SETTLING || s->state==SG_WAIT_CAPTURE) {
        if (!camera) return fail(s,"BOX_LEFT_BEFORE_CAPTURE_ACK");
        if (s->state==SG_SETTLING && now-s->since_ms>=s->config.settle_ms) {
            s->state=SG_WAIT_CAPTURE;s->since_ms=now;
            actions|=SG_CAPTURE;
        } else if (s->state==SG_WAIT_CAPTURE &&
                   now-s->since_ms>=s->config.capture_timeout_ms)
            return fail(s,"PI_CAPTURE_TIMEOUT");
    } else if (camera_rise) {
        if (s->box_id==UINT32_MAX) return fail(s,"ID_EXHAUSTED_REBOOT_EMPTY");
        if (s->count==SG_QUEUE_CAPACITY) return fail(s,"BOX_QUEUE_FULL");
        s->box_id++;s->capture_id=s->box_id;
        sg_box_t *box=&s->boxes[(s->head+s->count)%SG_QUEUE_CAPACITY];
        memset(box,0,sizeof(*box));box->id=s->box_id;s->count++;
        s->state=SG_SETTLING;s->since_ms=s->stopped_ms=now;
        actions|=motor_sync(s);
    }
    if (gate_rise) {
        sg_box_t *box=head_box(s);
        if (!box || !box->captured) return fail(s,"UNTRACKED_BOX_AT_GATE");
        if (s->gate_phase!=SG_GATE_IDLE)
            return fail(s,"SERVO_CYCLE_OVERLAP");
        s->gate_released=false;
        s->phase_ms=now;s->phase_motor_ms=s->motor_ms;
        if (box->result_ready) actions|=route_head(s,now);
        else {
            s->gate_phase=SG_GATE_WAIT_RESULT;
            actions|=motor_sync(s);
        }
    }
    if (gate_fall) {
        if (s->gate_phase==SG_GATE_WAIT_RESULT)
            return fail(s,"BOX_LEFT_GATE_WITHOUT_RESULT");
        s->gate_released=true;
        if (s->gate_phase==SG_GATE_PASSING || s->gate_phase==SG_GATE_WAIT_CLEAR)
            actions|=finish_head(s);
    }
    if (s->gate_phase!=SG_GATE_IDLE &&
        s->motor_ms-s->phase_motor_ms>=s->config.gate_timeout_ms)
        return fail(s,"GATE_SENSOR_STUCK");
    /* Several events can share one sample (camera arrival, previous sweep
       completion and next gate arrival). Emit only the final motor command. */
    if (actions&(SG_MOTOR_ON|SG_MOTOR_OFF)) {
        actions&=~(SG_MOTOR_ON|SG_MOTOR_OFF);
        actions|=s->motor_running ? SG_MOTOR_ON : SG_MOTOR_OFF;
    }
    return actions;
}
const char *sg_state_name(sg_state_t state) {
    static const char *names[]={"STOPPED","FEEDING","SETTLING","WAIT_CAPTURE","TO_GATE",
        "WAIT_AT_GATE","REJECTING","SERVO_RETURN","GATE_CLEAR","FAULT","JOG"};
    return state>=SG_STOPPED && state<=SG_JOG ? names[state] : "INVALID";
}
const char *sg_gate_name(sg_gate_phase_t phase) {
    static const char *names[]={"IDLE","WAIT_RESULT","PASSING","SWEEP_OUT","SWEEP_RETURN","WAIT_CLEAR"};
    return phase>=SG_GATE_IDLE && phase<=SG_GATE_WAIT_CLEAR ? names[phase] : "INVALID";
}
