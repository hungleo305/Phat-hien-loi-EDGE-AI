#ifndef STOPGO_H
#define STOPGO_H
#include <stdbool.h>
#include <stdint.h>

typedef enum { SG_STOPPED, SG_FEEDING, SG_SETTLING, SG_WAIT_CAPTURE,
    SG_TO_GATE, SG_WAIT_AT_GATE, SG_REJECTING, SG_SERVO_RETURN, SG_GATE_CLEAR, SG_FAULT, SG_JOG } sg_state_t;
typedef enum { SG_GATE_IDLE, SG_GATE_WAIT_RESULT, SG_GATE_PASSING,
    SG_GATE_SWEEP_OUT, SG_GATE_SWEEP_RETURN, SG_GATE_WAIT_CLEAR } sg_gate_phase_t;
typedef enum { SG_PASS, SG_DEFECT, SG_ERROR } sg_result_t;
enum { SG_MOTOR_ON=1, SG_MOTOR_OFF=2, SG_CAPTURE=4, SG_REJECT=8,
    SG_SERVO_HOME=16, SG_FINISHED=32, SG_ALARM=64, SG_ACCEPTED=128, SG_IMAGE_ACCEPTED=256, SG_JOG_DONE=512,
    SG_ROUTED=1024 };
#define SG_JOG_MAX_MS 2000U
#define SG_QUEUE_CAPACITY 8U
typedef struct {
    uint32_t settle_ms, result_timeout_ms, gate_timeout_ms, reject_ms, servo_return_ms, capture_timeout_ms;
} sg_config_t;
typedef struct {
    uint32_t id;
    uint64_t captured_ms;
    uint64_t captured_motor_ms;
    bool captured, result_ready, defect;
} sg_box_t;
typedef struct {
    sg_state_t state;
    sg_gate_phase_t gate_phase;
    sg_config_t config;
    uint32_t session, box_id, capture_id, result_id, finished_id;
    uint32_t jog_ms;
    uint64_t since_ms, stopped_ms, captured_ms, phase_ms;
    uint64_t motor_ms, last_clock_ms, phase_motor_ms;
    bool pi_ready, sorting_enabled, defect, previous_camera, previous_gate, result_ready, motor_running;
    bool gate_released;
    bool servo_moving; /* Actual command-ramp state, supplied by hardware adapter. */
    sg_box_t boxes[SG_QUEUE_CAPACITY];
    unsigned head, count;
    const char *fault;
} stopgo_t;

void sg_init(stopgo_t *s, uint32_t session, sg_config_t config);
unsigned sg_start(stopgo_t *s, uint64_t now, bool camera, bool gate);
unsigned sg_jog(stopgo_t *s, uint64_t now, uint32_t duration_ms, bool camera, bool gate);
unsigned sg_stop(stopgo_t *s);
bool sg_reset(stopgo_t *s, bool camera, bool gate);
unsigned sg_tick(stopgo_t *s, uint64_t now, bool camera, bool gate);
unsigned sg_result(stopgo_t *s, uint64_t now, uint32_t session, uint32_t id, sg_result_t result);
unsigned sg_captured(stopgo_t *s, uint64_t now, uint32_t session, uint32_t id);
const char *sg_state_name(sg_state_t state);
const char *sg_gate_name(sg_gate_phase_t phase);
#endif
