/*
=============================================================================
ĐỒ ÁN TỐT NGHIỆP KỸ SƯ - HỌC VIỆN KỸ THUẬT MẬT MÃ
CHUYÊN NGÀNH: AN TOÀN THÔNG TIN / HỆ THỐNG NHÚNG & EDGE AI
SINH VIÊN THỰC HIỆN: CHU MẠNH HÙNG

MÃ NGUỒN: 04_ESP32_Firmware/main/servo.c
CHỨC NĂNG: ĐIỀU KHIỂN TAY GẠT PHÂN LOẠI SERVO SG90 VỚI PROFILE 3 BƯỚC DỨT KHOÁT
THAM CHIẾU BÁO CÁO: MỤC 3.3.3 - ĐIỀU KHIỂN CƠ CẤU CHẤP HÀNH GẠT PHÂN LOẠI
=============================================================================

1. NGUYÊN LÝ ĐIỀU KHIỂN PWM (LEDC DRIVER TRÊN ESP32):
   - Tần số xung chuẩn cho RC Servo: f = 50Hz (Chu kỳ T = 20ms).
   - Độ phân giải Timer LEDC: 14-bit (2^14 = 16384 mức băm xung).
   - Vị trí gốc (HOME, 0 độ): Độ rộng xung tau = 1.50ms -> Duty = (1.5 / 20) * 16384 = 1229.
   - Vị trí gạt tối đa (90 độ): Độ rộng xung tau = 2.00ms -> Duty = (2.0 / 20) * 16384 = 1638.

2. PROFILE CHUYỂN ĐỘNG 3 BƯỚC DỨT KHOÁT (DECISIVE 3-STEP PROFILE):
   - Vấn đề thực tế: Servo giá rẻ SG90 có vùng chết analog (Deadband) và bánh răng nhựa
     dễ bị rung rơ nếu điều khiển góc mịn liên tục ở tần số cao (cháy động cơ hoặc kẹt bánh răng).
   - Giải pháp kỹ thuật: Áp dụng chuyển động 3 bước rời rạc với lực mô-men xoắn cực đại:
     + Bước 1: 0 độ -> 12 độ (Khởi động tay gạt)
     + Bước 2: 12 độ -> 23 độ (Tác dụng lực đẩy vào thành hộp)
     + Bước 3: 23 độ -> 35 độ (Hoàn tất đẩy hộp lỗi ra khỏi mặt băng tải)
   - Thời gian hoàn tất chu trình gạt chỉ ~150ms, triệt tiêu hoàn toàn hiện tượng rung giật.
=============================================================================
*/

#include "servo.h"
#include "app_config.h"
#include "driver/ledc.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include <inttypes.h>
#include <stdint.h>

static const char *TAG = "SERVO";

#define LEDC_TIMER LEDC_TIMER_2
#define LEDC_MODE LEDC_LOW_SPEED_MODE
#define LEDC_CHANNEL LEDC_CHANNEL_2
#define LEDC_DUTY_RES LEDC_TIMER_14_BIT
#define LEDC_FREQUENCY 50

/* 50 Hz, 14-bit LEDC: 1229 ~= 1.50 ms and 1638 ~= 2.00 ms.
   Preserve calibrated pulse neutral (1.50 ms) and 90 deg (2.00 ms). */
#define SERVO_DUTY_HOME 1229U
#define SERVO_DUTY_NINETY 1638U

#define SERVO_NUM_STEPS 3U

static unsigned reject_angle = SERVO_DEFAULT_REJECT_DEG;
static unsigned speed_dps = SERVO_DEFAULT_SPEED_DPS;
static int32_t position_mdeg = 0;
static int32_t start_mdeg = 0;
static int32_t target_mdeg = 0;
static uint32_t current_duty = SERVO_DUTY_HOME;
static uint64_t last_step_ms = 0;
static unsigned current_step = 0;
static bool moving = false;

static uint32_t duty_for_position(int32_t mdeg) {
  if (mdeg < 0)
    mdeg = 0;
  if (mdeg > 90000)
    mdeg = 90000;
  return SERVO_DUTY_HOME +
         ((SERVO_DUTY_NINETY - SERVO_DUTY_HOME) * (uint32_t)mdeg + 45000U) /
             90000U;
}

static void output_position(void) {
  uint32_t duty = duty_for_position(position_mdeg);
  if (duty == current_duty)
    return;
  ESP_ERROR_CHECK(ledc_set_duty(LEDC_MODE, LEDC_CHANNEL, duty));
  ESP_ERROR_CHECK(ledc_update_duty(LEDC_MODE, LEDC_CHANNEL));
  current_duty = duty;
}

static uint32_t calc_step_interval_ms(void) {
  if (speed_dps == 0)
    return 50U;
  uint32_t interval = (reject_angle * 1000U) / (SERVO_NUM_STEPS * speed_dps);
  if (interval < 30U)
    interval = 30U;
  if (interval > 100U)
    interval = 100U;
  return interval;
}

uint32_t servo_travel_ms(void) {
  return SERVO_NUM_STEPS * calc_step_interval_ms();
}

static void move_to(unsigned angle) {
  int32_t new_target = (int32_t)angle * 1000;
  if (new_target == position_mdeg && !moving) {
    return;
  }
  start_mdeg = position_mdeg;
  target_mdeg = new_target;
  int32_t dist = target_mdeg > start_mdeg ? target_mdeg - start_mdeg
                                          : start_mdeg - target_mdeg;
  if (dist == 0) {
    moving = false;
    current_step = 0;
    return;
  }
  moving = true;
  current_step = 1;
  last_step_ms = (uint64_t)(esp_timer_get_time() / 1000);

  /* Output Step 1 immediately: 1/3 of the way */
  int32_t delta = target_mdeg - start_mdeg;
  position_mdeg = start_mdeg + delta / (int32_t)SERVO_NUM_STEPS;
  output_position();

  ESP_LOGI(TAG,
           "Decisive sweep target=%u deg (step 1/%u: %d mdeg, interval=%" PRIu32
           " ms)",
           angle, (unsigned)SERVO_NUM_STEPS, (int)position_mdeg,
           calc_step_interval_ms());
}

void servo_service(uint64_t now_ms) {
  if (!moving)
    return;

  uint32_t interval_ms = calc_step_interval_ms();
  if (now_ms < last_step_ms || now_ms - last_step_ms < interval_ms) {
    return;
  }
  last_step_ms = now_ms;

  int32_t delta = target_mdeg - start_mdeg;

  if (current_step == 1) {
    /* Step 2: 2/3 of the way */
    current_step = 2;
    position_mdeg = start_mdeg + (2 * delta) / (int32_t)SERVO_NUM_STEPS;
    output_position();
  } else if (current_step == 2) {
    /* Step 3: Full target */
    current_step = 3;
    position_mdeg = target_mdeg;
    output_position();
  } else if (current_step >= 3) {
    /* Settle time for step 3 has elapsed */
    moving = false;
    current_step = 0;
    ESP_LOGI(TAG, "Decisive sweep complete at angle=%u deg",
             (unsigned)((position_mdeg + 500) / 1000));
  }
}

void servo_hold(void) {
  moving = false;
  current_step = 0;
  target_mdeg = position_mdeg;
  start_mdeg = position_mdeg;
  ESP_LOGW(TAG, "Motion held at commanded angle=%u deg",
           (unsigned)((position_mdeg + 500U) / 1000U));
}

void servo_init(int servo_pin) {
  reject_angle = SERVO_DEFAULT_REJECT_DEG;
  speed_dps = SERVO_DEFAULT_SPEED_DPS;
  position_mdeg = start_mdeg = target_mdeg = 0;
  moving = false;
  current_step = 0;
  current_duty = SERVO_DUTY_HOME;
  ledc_timer_config_t timer = {.speed_mode = LEDC_MODE,
                               .timer_num = LEDC_TIMER,
                               .duty_resolution = LEDC_DUTY_RES,
                               .freq_hz = LEDC_FREQUENCY,
                               .clk_cfg = LEDC_AUTO_CLK};
  ESP_ERROR_CHECK(ledc_timer_config(&timer));
  ledc_channel_config_t channel = {.speed_mode = LEDC_MODE,
                                   .channel = LEDC_CHANNEL,
                                   .timer_sel = LEDC_TIMER,
                                   .intr_type = LEDC_INTR_DISABLE,
                                   .gpio_num = servo_pin,
                                   .duty = SERVO_DUTY_HOME,
                                   .hpoint = 0};
  ESP_ERROR_CHECK(ledc_channel_config(&channel));
  ESP_LOGI(TAG,
           "Home=0 deg duty=%u, reject=%u deg duty=%" PRIu32
           ", decisive 3-step interval=%" PRIu32 " ms",
           SERVO_DUTY_HOME, reject_angle,
           duty_for_position((int32_t)reject_angle * 1000),
           calc_step_interval_ms());
}

void servo_reset(void) { move_to(0); }

void servo_reject(void) { move_to(reject_angle); }

bool servo_set_reject_angle(unsigned angle) {
  if (moving || angle < 1 || angle > SERVO_MAX_TEST_DEG)
    return false;
  reject_angle = angle;
  ESP_LOGW(TAG, "Reject angle set to %u deg for this boot only", angle);
  return true;
}

bool servo_preview_angle(unsigned angle) {
  if (angle > SERVO_MAX_TEST_DEG)
    return false;
  move_to(angle);
  return true;
}

unsigned servo_reject_angle(void) { return reject_angle; }
unsigned servo_current_angle(void) {
  return (unsigned)((position_mdeg + 500U) / 1000U);
}
bool servo_is_moving(void) { return moving; }

bool servo_set_speed(unsigned degrees_per_second) {
  if (moving || degrees_per_second < SERVO_MIN_SPEED_DPS ||
      degrees_per_second > SERVO_MAX_SPEED_DPS)
    return false;
  speed_dps = degrees_per_second;
  return true;
}

unsigned servo_speed(void) { return speed_dps; }
