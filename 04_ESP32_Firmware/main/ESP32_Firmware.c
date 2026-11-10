#include "app_config.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "led.h"
#include "motor.h"
#include "protocol.h"
#include "sensor.h"
#include "servo.h"
#include "stopgo.h"
#include "uart.h"
#include <inttypes.h>

/* Single application task: sensors -> FSM/FIFO -> actuators -> Pi UART2.
 * UART0 remains available for ESP-IDF diagnostic output only.
 * Keep all waits nonblocking except the short scheduler delay below.
 */
static stopgo_t machine;
static uint32_t requested_out_ms = SERVO_REJECT_MS;
static uint32_t last_operator_sequence;
static uint64_t last_operator_ping_ms;
static bool have_operator_ping;
static bool operator_running;
typedef struct {
  bool candidate, stable;
  uint64_t changed;
} debounce_t;
static uint64_t now_ms(void) { return (uint64_t)(esp_timer_get_time() / 1000); }
static void update_servo_timing(void) {
  uint32_t required = servo_travel_ms() + SERVO_ENDPOINT_ALLOWANCE_MS;
  machine.config.reject_ms =
      requested_out_ms > required ? requested_out_ms : required;
  machine.config.servo_return_ms =
      SERVO_RETURN_MS > required ? SERVO_RETURN_MS : required;
}
static bool sample(debounce_t *s, bool raw, uint64_t now) {
  if (raw != s->candidate) {
    s->candidate = raw;
    s->changed = now;
  }
  if (now - s->changed >= SENSOR_DEBOUNCE_MS)
    s->stable = s->candidate;
  return s->stable;
}
static void act(unsigned actions, uint64_t now) {
  if (actions & SG_MOTOR_OFF)
    motor_stop();
  if (actions & SG_ALARM)
    servo_hold();
  if (actions & SG_SERVO_HOME)
    servo_reset();
  if (actions & SG_REJECT)
    servo_reject();
  if (actions & SG_ROUTED) {
    const sg_box_t *box = &machine.boxes[machine.head];
    ESP_LOGI("STOPGO", "GATE id=%" PRIu32 " decision=%s action=%s queue=%u",
             box->id, box->defect ? "DEFECT" : "PASS",
             (actions & SG_REJECT)
                 ? "SWEEP_NOW"
                 : (box->defect ? "DRY_PASS" : "PASS_THROUGH"),
             machine.count);
  }
  if (actions & SG_CAPTURE) {
    ESP_LOGI("STOPGO",
             "CAPTURE session=%" PRIu32 " id=%" PRIu32 " settle_ms=%" PRIu64,
             machine.session, machine.capture_id, now - machine.stopped_ms);
    if (!uart_send_capture_command(machine.session, machine.capture_id)) {
      act(sg_stop(&machine), now);
      return;
    }
  }
  if (actions & SG_ACCEPTED)
    ESP_LOGI("STOPGO", "RESULT id=%" PRIu32 " %s queue=%u", machine.result_id,
             machine.defect ? "DEFECT" : "PASS", machine.count);
  if (actions & SG_IMAGE_ACCEPTED)
    ESP_LOGI("STOPGO",
             "CAPTURED id=%" PRIu32 " stop_to_captured_ms=%" PRIu64
             " motor=%d; AI async",
             machine.capture_id, now - machine.stopped_ms,
             machine.motor_running);
  if (actions & SG_MOTOR_ON)
    motor_start();
  if (actions & SG_JOG_DONE)
    ESP_LOGI(
        "STOPGO",
        "JOG stopped: duration elapsed, sensor active or m0; state=STOPPED");
  if (actions & SG_FINISHED)
    ESP_LOGI("STOPGO", "DONE id=%" PRIu32 " mode=%s", machine.finished_id,
             machine.sorting_enabled ? "SORT" : "DRY_NO_SERVO");
  if (actions & SG_ALARM)
    ESP_LOGE("STOPGO",
             "FAULT id=%" PRIu32 " %s newest_id=%" PRIu32
             " gate_phase=%s last_done_id=%" PRIu32 " phase_motor_ms=%" PRIu64
             " sweep_out_ms=%" PRIu32
             " servo_held=%u; clear whole belt before dashboard STOP",
             machine.count ? machine.boxes[machine.head].id : machine.box_id,
             machine.fault, machine.box_id, sg_gate_name(machine.gate_phase),
             machine.finished_id, machine.motor_ms - machine.phase_motor_ms,
             machine.config.reject_ms, servo_current_angle());
  machine.servo_moving = servo_is_moving();
}
static void send_state(bool tick_camera, bool tick_gate) {
  uart_send_state(
      machine.session, sg_state_name(machine.state), machine.motor_running,
      machine.sorting_enabled, machine.pi_ready, tick_camera, tick_gate,
      machine.count, machine.box_id, machine.state == SG_FAULT,
      motor_speed(), led_brightness(), servo_reject_angle(), servo_speed(),
      requested_out_ms, machine.config.reject_ms, servo_is_moving());
}

/* Only this task owns machine and the actuator state. */
static void handle_operator(const op_message_t *op, uint64_t now,
                            bool tick_camera, bool tick_gate) {
  bool accepted = false;
  if (op->session == machine.session &&
      op->sequence != last_operator_sequence) {
    last_operator_sequence = op->sequence;
    bool clear = !tick_camera && !tick_gate &&
                 !is_camera_sensor_triggered() && !is_ir_triggered();
    if (op->verb == OP_STOP) {
      act(sg_stop(&machine), now);
      operator_running = false;
      accepted = true;
    } else if (op->verb == OP_START && clear && motor_speed() > 0 &&
               led_brightness() > 0 && have_operator_ping &&
               now - last_operator_ping_ms < 1500 && !servo_is_moving() &&
               servo_current_angle() == 0) {
      unsigned actions = sg_start(&machine, now, false, false);
      if (actions) {
        act(actions, now);
        operator_running = true;
        accepted = true;
      }
    } else if ((op->verb == OP_DRY || op->verb == OP_SORT) &&
               machine.state == SG_STOPPED && !machine.count && clear) {
      machine.sorting_enabled = op->verb == OP_SORT;
      accepted = true;
    } else if ((op->verb == OP_SPEED || op->verb == OP_LIGHT) &&
               machine.state == SG_STOPPED && !machine.count && clear &&
               !servo_is_moving()) {
      if (op->verb == OP_SPEED)
        motor_set_speed((uint8_t)op->value);
      else
        led_set_brightness((uint8_t)op->value);
      accepted = true;
    } else if ((op->verb == OP_SERVO_ANGLE || op->verb == OP_SERVO_SPEED ||
                op->verb == OP_SERVO_HOLD) &&
               machine.state == SG_STOPPED && !machine.motor_running &&
               !machine.count && clear && !servo_is_moving() &&
               servo_current_angle() == 0) {
      if (op->verb == OP_SERVO_ANGLE)
        accepted = servo_set_reject_angle((unsigned)op->value);
      else if (op->verb == OP_SERVO_SPEED)
        accepted = servo_set_speed((unsigned)op->value);
      else if (op->value >= SERVO_OUT_MIN_MS &&
               op->value <= SERVO_OUT_MAX_MS) {
        requested_out_ms = op->value;
        accepted = true;
      }
      if (accepted)
        update_servo_timing();
    } else if (op->verb == OP_STATUS)
      accepted = true;
  }
  uart_send_operator_ack(machine.session, op->sequence, accepted);
  send_state(tick_camera, tick_gate);
  ESP_LOGW("DASHBOARD", "OP %" PRIu32 " %s", op->sequence,
           accepted ? "OK" : "DENY");
}

static void process_pi_messages(uint64_t now, bool tick_camera, bool tick_gate) {
  char line[PI_LINE_SIZE];
  for (int i = 0; i < 8 && uart_read_message(line, sizeof(line)); i++) {
    uint32_t ping_session;
    if (pi_parse_ping(line, &ping_session)) {
      if (ping_session == machine.session) {
        last_operator_ping_ms = now;
        have_operator_ping = true;
      }
      continue;
    }
    op_message_t op;
    if (pi_parse_operator(line, &op)) {
      handle_operator(&op, now, tick_camera, tick_gate);
      continue;
    }
    pi_message_t message;
    if (!pi_parse(line, &message)) {
      ESP_LOGW("UART", "Invalid protocol line ignored");
      continue;
    }
    if (message.type == PI_READY && message.session == machine.session &&
        machine.state == SG_STOPPED) {
      machine.pi_ready = true;
      ESP_LOGI("UART", "Pi READY for this boot session");
    } else if (message.type == PI_CAPTURED) {
      unsigned actions =
          sg_captured(&machine, now, message.session, message.id);
      if (!actions)
        ESP_LOGW("UART", "Stale/unexpected CAPTURED ignored");
      act(actions, now);
    } else if (message.type == PI_RESULT) {
      unsigned actions = sg_result(&machine, now, message.session, message.id,
                                   message.result);
      if (!actions)
        ESP_LOGW("UART",
                 "Stale/unexpected result ignored session=%" PRIu32
                 " id=%" PRIu32,
                 message.session, message.id);
      act(actions, now);
    }
  }
}

static void control_task(void *unused) {
  (void)unused;
  debounce_t cam = {0}, ir = {0};
  uint64_t hello_at = 0, state_at = 0;
  uint64_t gate_enter_motion = 0, gate_release_motion = 0;
  bool have_gate_release = false;
  for (;;) {
    /* 1. Sample hardware and advance the nonblocking machine. */
    uint64_t now = now_ms();
    servo_service(now);
    machine.servo_moving = servo_is_moving();
    bool raw_camera = is_camera_sensor_triggered();
    bool raw_gate = is_ir_triggered();
    bool camera = sample(&cam, raw_camera, now);
    bool gate = sample(&ir, raw_gate, now);
    /* Detect an object on its first active sample so a moving box cannot be
       missed. Keep the filtered value active while the release settles. */
    bool tick_camera = camera || raw_camera;
    bool tick_gate = gate || raw_gate;
    bool gate_enter = tick_gate && !machine.previous_gate;
    bool gate_release = !tick_gate && machine.previous_gate;
    bool running_cycle = machine.state != SG_STOPPED &&
                         machine.state != SG_FAULT && machine.state != SG_JOG;
    unsigned tick_actions = sg_tick(&machine, now, tick_camera, tick_gate);
    if (running_cycle && gate_enter) {
      gate_enter_motion = machine.motor_ms;
      ESP_LOGI("STOPGO", "IR_ENTER gap_motor_ms=%" PRIu64 " gap_valid=%d",
               have_gate_release ? machine.motor_ms - gate_release_motion : 0,
               have_gate_release);
    }
    if (running_cycle && gate_release) {
      ESP_LOGI("STOPGO", "IR_RELEASE occupied_motor_ms=%" PRIu64,
               machine.motor_ms - gate_enter_motion);
      gate_release_motion = machine.motor_ms;
      have_gate_release = true;
    }
    if (!running_cycle)
      have_gate_release = false;
    act(tick_actions, now);
    /* 2. Enforce heartbeat before accepting new commands. */
    if (operator_running && now - last_operator_ping_ms > 2000) {
      act(sg_stop(&machine), now);
      operator_running = false;
      ESP_LOGE(
          "DASHBOARD",
          "Pi heartbeat lost; motor stopped, clear conveyor before restart");
    }
    if (machine.state == SG_STOPPED || machine.state == SG_FAULT)
      operator_running = false;
    /* 3. Receive bounded UART2 work, then publish status. */
    process_pi_messages(now, tick_camera, tick_gate);
    if (machine.state == SG_STOPPED && now - hello_at >= 1000) {
      uart_send_hello(machine.session);
      hello_at = now;
    }
    if (now - state_at >= 500) {
      send_state(tick_camera, tick_gate);
      state_at = now;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}
void app_main(void) {
  motor_init(MOTOR_IN1_PIN, MOTOR_IN2_PIN, MOTOR_ENA_PIN);
  motor_stop();
  motor_set_speed(INITIAL_MOTOR_SPEED);
  led_init(LED_IN3_PIN, LED_IN4_PIN, LED_ENB_PIN);
  led_set_brightness(INITIAL_LED_BRIGHTNESS);
  servo_init(SERVO_PIN);
  sensor_init(CAMERA_SENSOR_PIN, IR_SENSOR_PIN);
  uart_pi_init(UART_TX_PIN, UART_RX_PIN, UART_PORT_NUM, UART_BAUD_RATE);
  sg_config_t config = {BOX_SETTLE_MS,           PI_RESULT_TIMEOUT_MS,
                        GATE_TRANSIT_TIMEOUT_MS, SERVO_REJECT_MS,
                        SERVO_RETURN_MS,         PI_CAPTURE_TIMEOUT_MS};
  sg_init(&machine, esp_random(), config);
  update_servo_timing();
  ESP_LOGW("STOPGO", "Build SINGLE_TASK_UART2_20261109. Boot STOPPED, "
                     "sorting OFF. Dashboard control over Pi UART2; no UART0 commands");
  configASSERT(xTaskCreate(control_task, "stopgo", 6144, NULL, 5, NULL) ==
               pdPASS);
}
