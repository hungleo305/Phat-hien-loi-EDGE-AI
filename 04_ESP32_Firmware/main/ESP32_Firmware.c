/*
=============================================================================
ĐỒ ÁN TỐT NGHIỆP KỸ SƯ - HỌC VIỆN KỸ THUẬT MẬT MÃ
CHUYÊN NGÀNH: AN TOÀN THÔNG TIN / HỆ THỐNG NHÚNG & EDGE AI
SINH VIÊN THỰC HIỆN: CHU MẠNH HÙNG

MÃ NGUỒN: 04_ESP32_Firmware/main/ESP32_Firmware.c
CHỨC NĂNG: FIRMWARE ĐIỀU KHIỂN THỜI GIAN THỰC BĂNG TẢI & CƠ CẤU CHẤP HÀNH (ESP32)
THAM CHIẾU BÁO CÁO: MỤC 3.3 - THIẾT KẾ PHẦN MỀM NHÚNG VI ĐIỀU KHIỂN ESP32
=============================================================================

1. KIẾN TRÚC HỆ THỐNG ĐIỀU KHIỂN PHÂN TÁN (DISTRIBUTED EMBEDDED ARCHITECTURE):
   - Hệ thống áp dụng mô hình phân tách vai trò:
     + Raspberry Pi 4: Master Controller - Đảm nhiệm Edge AI nặng, thị giác máy tính,
       quản lý cơ sở dữ liệu và Web Server SCADA giám sát.
     + ESP32 DevKit: Slave Real-time Controller - Đảm nhiệm điều khiển cứng thời gian thực:
       động cơ DC băng tải, cơ cấu gạt servo SG90, điều chế độ sáng đèn LED công nghiệp,
       quét cảm biến quang điện hồng ngoại (30ms debounce), và giao thức UART an toàn.

2. CÁC TÁC VỤ FREERTOS (FREERTOS MULTI-TASKING):
   - control_task (Priority 5 - Cao nhất, 6144 bytes stack):
     + Chu kỳ lặp 10ms (100Hz).
     + Chạy Máy trạng thái hữu hạn Stop & Go (FSM 10 trạng thái từ SG_STOPPED đến SG_FAULT).
     + Duy trì hàng đợi FIFO theo dõi tối đa 8 vỏ hộp di chuyển giữa 2 cảm biến.
     + Gửi nhịp tim (Heartbeat) và gói tin trạng thái STATE định kỳ 500ms cho Pi 4.
   - console_task (Priority 4, 3072 bytes stack):
     + Lắng nghe cổng nạp USB UART0 để nhận lệnh gỡ lỗi thủ công từ kỹ thuật viên.
     + Chuyển lệnh an toàn qua hàng đợi FreeRTOS console_commands (dung lượng 8 lệnh).
=============================================================================
*/

#include "app_config.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "led.h"
#include "motor.h"
#include "protocol.h"
#include "sensor.h"
#include "servo.h"
#include "stopgo.h"
#include "uart.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static stopgo_t machine;
static uint32_t requested_out_ms = SERVO_REJECT_MS;
static QueueHandle_t console_commands;
static uint32_t last_operator_sequence;
static uint64_t last_operator_ping_ms;
static bool have_operator_ping;
static bool operator_running;
typedef struct {
  char text[64];
} console_command_t;
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
             " servo_held=%u; clear whole belt before reset/m0",
             machine.count ? machine.boxes[machine.head].id : machine.box_id,
             machine.fault, machine.box_id, sg_gate_name(machine.gate_phase),
             machine.finished_id, machine.motor_ms - machine.phase_motor_ms,
             machine.config.reject_ms, servo_current_angle());
  machine.servo_moving = servo_is_moving();
}
static bool bounded_value(const char *text, unsigned maximum, int *out) {
  if (!*text)
    return false;
  unsigned n = 0;
  for (; *text; text++) {
    if (*text < '0' || *text > '9')
      return false;
    unsigned digit = (unsigned)(*text - '0');
    if (n > maximum / 10 || (n == maximum / 10 && digit > maximum % 10))
      return false;
    n = n * 10 + digit;
  }
  *out = (int)n;
  return true;
}
static bool value(const char *text, int *out) {
  return bounded_value(text, 255, out);
}
static void command(const char *text, uint64_t now, bool camera, bool gate) {
  int n;
  if (strcmp(text, "m0") == 0) {
    act(sg_stop(&machine), now);
    ESP_LOGW("STOPGO", "Operator stop OK; tracking cleared. Remove all boxes "
                       "and clear sensors before m1");
  } else if (strncmp(text, "jog", 3) == 0 &&
             bounded_value(text + 3, SG_JOG_MAX_MS, &n)) {
    if (servo_is_moving() || servo_current_angle() != 0) {
      ESP_LOGW("STOPGO",
               "JOG refused: wait for servo0 home command to complete");
      return;
    }
    unsigned actions = sg_jog(&machine, now, (uint32_t)n,
                              camera || is_camera_sensor_triggered(),
                              gate || is_ir_triggered());
    if (actions)
      ESP_LOGW("STOPGO",
               "JOG %d ms: hardware motor test, no Pi needed; m0 or sensor "
               "stops early",
               n);
    else
      ESP_LOGW("STOPGO", "JOG refused: require STOPPED, g0, clear sensors, "
                         "duration 1..2000 ms");
    act(actions, now);
  } else if (strcmp(text, "m1") == 0) {
    if (servo_is_moving()) {
      ESP_LOGW("STOPGO",
               "Start refused: servo is moving; wait for home, then m1");
      return;
    }
    if (machine.state == SG_STOPPED && !machine.count && !camera && !gate &&
        !is_camera_sensor_triggered() && !is_ir_triggered() &&
        servo_current_angle() != 0) {
      servo_reset();
      machine.servo_moving = servo_is_moving();
      ESP_LOGW("STOPGO", "Servo homing; motor stays stopped. Wait, then m1");
      return;
    }
    unsigned actions =
        sg_start(&machine, now, camera || is_camera_sensor_triggered(),
                 gate || is_ir_triggered());
    if (!actions)
      ESP_LOGW("STOPGO", "Start refused: need STOPPED + READY + both sensors "
                         "clear; reset faults first");
    else
      servo_reset();
    act(actions, now);
  } else if (strcmp(text, "reset") == 0) {
    if (sg_reset(&machine, camera || is_camera_sensor_triggered(),
                 gate || is_ir_triggered())) {
      servo_reset();
      ESP_LOGI("STOPGO",
               "Reset OK; stopped. Inspect/clear whole conveyor, then m1");
    } else
      ESP_LOGW("STOPGO", "Reset refused: stop and clear both sensors first");
  } else if (strcmp(text, "status") == 0) {
    ESP_LOGI("STOPGO",
             "state=%s gate_phase=%s session=%" PRIu32 " id=%" PRIu32
             " queue=%u ready=%d camera=%d gate=%d sort=%d motor=%d servo=%u "
             "reject=%u servo_speed_dps=%u servo_moving=%d out_min_ms=%" PRIu32
             " sweep_out_ms=%" PRIu32 " return_ms=%" PRIu32
             " fault=%s raw_camera=%d raw_gate=%d",
             sg_state_name(machine.state), sg_gate_name(machine.gate_phase),
             machine.session, machine.box_id, machine.count, machine.pi_ready,
             camera, gate, machine.sorting_enabled, machine.motor_running,
             servo_current_angle(), servo_reject_angle(), servo_speed(),
             servo_is_moving(), requested_out_ms, machine.config.reject_ms,
             machine.config.servo_return_ms,
             machine.fault ? machine.fault : "none",
             is_camera_sensor_triggered(), is_ir_triggered());
  } else if ((strcmp(text, "g0") == 0 || strcmp(text, "g1") == 0) &&
             machine.state == SG_STOPPED) {
    machine.sorting_enabled = text[1] == '1';
    ESP_LOGW("STOPGO", "Servo sorting %s",
             machine.sorting_enabled ? "ENABLED" : "DISABLED (dry test)");
  } else if (strncmp(text, "ss", 2) == 0 &&
             bounded_value(text + 2, SERVO_MAX_SPEED_DPS, &n)) {
    if (machine.state == SG_STOPPED && !machine.count && !camera && !gate &&
        !is_camera_sensor_triggered() && !is_ir_triggered() &&
        servo_set_speed((unsigned)n)) {
      update_servo_timing();
      ESP_LOGW("STOPGO",
               "Soft speed=%u deg/s, reject=%u deg unchanged; out_ms=%" PRIu32
               " return_ms=%" PRIu32 "; for this boot",
               servo_speed(), servo_reject_angle(), machine.config.reject_ms,
               machine.config.servo_return_ms);
    } else
      ESP_LOGW("STOPGO",
               "ss refused: require STOPPED, empty sensors/FIFO, servo not "
               "moving, %d..%d deg/s",
               SERVO_MIN_SPEED_DPS, SERVO_MAX_SPEED_DPS);
  } else if (strncmp(text, "gh", 2) == 0 &&
             bounded_value(text + 2, SERVO_OUT_MAX_MS, &n)) {
    if (machine.state == SG_STOPPED && !machine.count && !camera && !gate &&
        !is_camera_sensor_triggered() && !is_ir_triggered() &&
        !servo_is_moving() && n >= SERVO_OUT_MIN_MS) {
      requested_out_ms = (uint32_t)n;
      update_servo_timing();
      ESP_LOGW("STOPGO",
               "OUT minimum=%d ms, effective out_ms=%" PRIu32
               " return_ms=%" PRIu32 "; soft travel cannot be cut short",
               n, machine.config.reject_ms, machine.config.servo_return_ms);
    } else
      ESP_LOGW("STOPGO",
               "gh refused: require STOPPED, empty belt/sensors and %d..%d ms",
               SERVO_OUT_MIN_MS, SERVO_OUT_MAX_MS);
  } else if (strncmp(text, "sr", 2) == 0 &&
             bounded_value(text + 2, SERVO_MAX_TEST_DEG, &n)) {
    if (machine.state == SG_STOPPED && !machine.count && !camera && !gate &&
        !is_camera_sensor_triggered() && !is_ir_triggered() &&
        servo_set_reject_angle((unsigned)n)) {
      update_servo_timing();
      ESP_LOGI(
          "STOPGO",
          "Reject target=%d deg; speed=%u deg/s; test with servo1, then servo0",
          n, servo_speed());
    } else
      ESP_LOGW(
          "STOPGO",
          "sr refused: require STOPPED, empty belt/sensors and angle 1..%d",
          SERVO_MAX_TEST_DEG);
  } else if (strncmp(text, "sv", 2) == 0 &&
             bounded_value(text + 2, SERVO_MAX_TEST_DEG, &n)) {
    if (machine.state == SG_STOPPED && !machine.count && !camera && !gate &&
        !is_camera_sensor_triggered() && !is_ir_triggered() &&
        !servo_is_moving())
      servo_preview_angle((unsigned)n);
    else
      ESP_LOGW("STOPGO", "sv refused: require STOPPED and empty belt/sensors");
  } else if (strcmp(text, "servo1") == 0 && machine.state == SG_STOPPED &&
             !machine.count && !camera && !gate &&
             !is_camera_sensor_triggered() && !is_ir_triggered() &&
             !servo_is_moving()) {
    servo_reject();
    ESP_LOGW("STOPGO", "Manual servo reject position; motor remains STOPPED. "
                       "Type servo0 to home");
  } else if (strcmp(text, "servo0") == 0 && machine.state == SG_STOPPED) {
    servo_reset();
  } else if (text[0] == 's' && value(text + 1, &n)) {
    if (machine.state == SG_STOPPED)
      motor_set_speed((uint8_t)n);
    else
      ESP_LOGW("STOPGO", "Change speed only while STOPPED");
  } else if (text[0] == 'l' && value(text + 1, &n)) {
    if (machine.state == SG_STOPPED)
      led_set_brightness((uint8_t)n);
    else
      ESP_LOGW("STOPGO", "Change illumination only while STOPPED");
  } else
    ESP_LOGW("STOPGO",
             "Commands: status | jog1..2000 | m0 | reset | m1 | s0..255 | "
             "l0..255 | g0/g1 | servo0/servo1 | sv0..90 | sr1..90 | ss30..240 "
             "(deg/s) | gh150..1500 (minimum OUT ms; stopped)");
}
static void control_task(void *unused) {
  (void)unused;
  debounce_t cam = {0}, ir = {0};
  uint64_t hello_at = 0, state_at = 0;
  uint64_t gate_enter_motion = 0, gate_release_motion = 0;
  bool have_gate_release = false;
  for (;;) {
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
    if (operator_running && now - last_operator_ping_ms > 2000) {
      act(sg_stop(&machine), now);
      operator_running = false;
      ESP_LOGE(
          "DASHBOARD",
          "Pi heartbeat lost; motor stopped, clear conveyor before restart");
    }
    if (machine.state == SG_STOPPED || machine.state == SG_FAULT)
      operator_running = false;
    console_command_t cmd;
    for (int i = 0; i < 8 && xQueueReceive(console_commands, &cmd, 0) == pdTRUE;
         i++)
      command(cmd.text, now, camera, gate);
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
        bool accepted = false;
        if (op.session == machine.session &&
            op.sequence != last_operator_sequence) {
          last_operator_sequence = op.sequence;
          bool clear = !tick_camera && !tick_gate &&
                       !is_camera_sensor_triggered() && !is_ir_triggered();
          if (op.verb == OP_STOP) {
            act(sg_stop(&machine), now);
            operator_running = false;
            accepted = true;
          } else if (op.verb == OP_START && clear && motor_speed() > 0 &&
                     led_brightness() > 0 && have_operator_ping &&
                     now - last_operator_ping_ms < 1500 && !servo_is_moving() &&
                     servo_current_angle() == 0) {
            unsigned actions = sg_start(&machine, now, false, false);
            if (actions) {
              act(actions, now);
              operator_running = true;
              accepted = true;
            }
          } else if ((op.verb == OP_DRY || op.verb == OP_SORT) &&
                     machine.state == SG_STOPPED && !machine.count && clear) {
            machine.sorting_enabled = op.verb == OP_SORT;
            accepted = true;
          } else if ((op.verb == OP_SPEED || op.verb == OP_LIGHT) &&
                     machine.state == SG_STOPPED && !machine.count && clear &&
                     !servo_is_moving()) {
            if (op.verb == OP_SPEED)
              motor_set_speed((uint8_t)op.value);
            else
              led_set_brightness((uint8_t)op.value);
            accepted = true;
          } else if ((op.verb == OP_SERVO_ANGLE || op.verb == OP_SERVO_SPEED ||
                      op.verb == OP_SERVO_HOLD) &&
                     machine.state == SG_STOPPED && !machine.motor_running &&
                     !machine.count && clear && !servo_is_moving() &&
                     servo_current_angle() == 0) {
            if (op.verb == OP_SERVO_ANGLE)
              accepted = servo_set_reject_angle((unsigned)op.value);
            else if (op.verb == OP_SERVO_SPEED)
              accepted = servo_set_speed((unsigned)op.value);
            else if (op.value >= SERVO_OUT_MIN_MS &&
                     op.value <= SERVO_OUT_MAX_MS) {
              requested_out_ms = op.value;
              accepted = true;
            }
            if (accepted)
              update_servo_timing();
          } else if (op.verb == OP_STATUS)
            accepted = true;
        }
        uart_send_operator_ack(machine.session, op.sequence, accepted);
        uart_send_state(machine.session, sg_state_name(machine.state),
                        machine.motor_running, machine.sorting_enabled,
                        machine.pi_ready, tick_camera, tick_gate, machine.count,
                        machine.box_id, machine.state == SG_FAULT,
                        motor_speed(), led_brightness(), servo_reject_angle(),
                        servo_speed(), requested_out_ms,
                        machine.config.reject_ms, servo_is_moving());
        ESP_LOGW("DASHBOARD", "OP %" PRIu32 " %s", op.sequence,
                 accepted ? "OK" : "DENY");
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
    if (machine.state == SG_STOPPED && now - hello_at >= 1000) {
      uart_send_hello(machine.session);
      hello_at = now;
    }
    if (now - state_at >= 500) {
      uart_send_state(
          machine.session, sg_state_name(machine.state), machine.motor_running,
          machine.sorting_enabled, machine.pi_ready, tick_camera, tick_gate,
          machine.count, machine.box_id, machine.state == SG_FAULT,
          motor_speed(), led_brightness(), servo_reject_angle(), servo_speed(),
          requested_out_ms, machine.config.reject_ms, servo_is_moving());
      state_at = now;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}
static void console_task(void *unused) {
  (void)unused;
  char line[64];
  size_t used = 0;
  bool discard = false;
  for (;;) {
    unsigned char ch;
    int got = uart_read_bytes(UART_NUM_0, &ch, 1, pdMS_TO_TICKS(20));
    if (got != 1)
      continue;
    if (ch == '\r' || ch == '\n') {
      if (used && !discard) {
        console_command_t command = {0};
        memcpy(command.text, line, used);
        if (xQueueSend(console_commands, &command, 0) != pdTRUE)
          ESP_LOGW("CONSOLE", "Queue full; command refused");
      }
      used = 0;
      discard = false;
    } else if (ch == 8 || ch == 127) {
      if (used && !discard)
        used--;
    } else if (ch < 32 || ch > 126 || used >= sizeof(line) - 1)
      discard = true;
    else if (!discard)
      line[used++] = (char)ch;
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
  ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0));
  console_commands = xQueueCreate(8, sizeof(console_command_t));
  configASSERT(console_commands);
  sg_config_t config = {BOX_SETTLE_MS,           PI_RESULT_TIMEOUT_MS,
                        GATE_TRANSIT_TIMEOUT_MS, SERVO_REJECT_MS,
                        SERVO_RETURN_MS,         PI_CAPTURE_TIMEOUT_MS};
  sg_init(&machine, esp_random(), config);
  update_servo_timing();
  ESP_LOGW("STOPGO", "Build FIFO_DASHBOARD_SERVO_PULSE_20261027. Boot STOPPED, "
                     "sorting OFF. Web settings use Pi UART2 with heartbeat");
  ESP_LOGW("STOPGO",
           "Build FIFO_DASHBOARD_SERVO_DECISIVE_20261031. Boot STOPPED, "
           "sorting OFF. Web settings use Pi UART2 with heartbeat");
  configASSERT(xTaskCreate(control_task, "stopgo", 6144, NULL, 5, NULL) ==
               pdPASS);
  configASSERT(xTaskCreate(console_task, "console", 3072, NULL, 4, NULL) ==
               pdPASS);
}
