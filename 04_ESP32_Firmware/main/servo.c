/* LEDC holds the target PWM; service only tracks estimated travel time.
 * SG90 has no physical position feedback. No blocking wait or servo task. */
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

static unsigned reject_angle = SERVO_DEFAULT_REJECT_DEG;
static unsigned speed_dps = SERVO_DEFAULT_SPEED_DPS;
static int32_t position_mdeg = 0;
static int32_t target_mdeg = 0;
static uint32_t current_duty = SERVO_DUTY_HOME;
static uint64_t last_step_ms = 0;
static bool moving = false;

static uint32_t duty_for_position(int32_t mdeg) {
  if (mdeg < 0)
    mdeg = 0;
  if (mdeg > 90000)
    mdeg = 90000;
  uint32_t delta =
      ((SERVO_DUTY_NINETY - SERVO_DUTY_HOME) * (uint32_t)mdeg + 45000U) /
      90000U;
#if defined(SERVO_REVERSE_DIRECTION) && (SERVO_REVERSE_DIRECTION == 1)
  return (SERVO_DUTY_HOME >= delta) ? (SERVO_DUTY_HOME - delta) : 0;
#else
  return SERVO_DUTY_HOME + delta;
#endif
}

static void output_position(void) {
  uint32_t duty = duty_for_position(position_mdeg);
  if (duty == current_duty)
    return;
  ESP_ERROR_CHECK(ledc_set_duty(LEDC_MODE, LEDC_CHANNEL, duty));
  ESP_ERROR_CHECK(ledc_update_duty(LEDC_MODE, LEDC_CHANNEL));
  current_duty = duty;
}

uint32_t servo_travel_ms(void) {
  /* SG90 physical transit time for ~35-50 deg is approx 60-80 ms */
  uint32_t t = (reject_angle * 1000U) / (speed_dps > 0 ? speed_dps : 230U);
  if (t < 60U) t = 60U;
  if (t > 150U) t = 150U;
  return t;
}

static void move_to(unsigned angle) {
  int32_t new_target = (int32_t)angle * 1000;
  if (new_target == position_mdeg && !moving) {
    return;
  }

  target_mdeg = new_target;
  if (target_mdeg == position_mdeg) {
    moving = false;
    return;
  }
  moving = true;
  last_step_ms = (uint64_t)(esp_timer_get_time() / 1000);

  /* Output target position IMMEDIATELY and DECISIVELY in one single sweep (no stuttering intermediate steps) */
  position_mdeg = target_mdeg;
  output_position();

  ESP_LOGI(TAG,
           "Decisive direct sweep target=%u deg (duty=%" PRIu32 ", travel=%" PRIu32 " ms)",
           angle, duty_for_position(position_mdeg), servo_travel_ms());
}

void servo_service(uint64_t now_ms) {
  if (!moving)
    return;

  if (now_ms < last_step_ms || now_ms - last_step_ms >= servo_travel_ms()) {
    moving = false;

    ESP_LOGI(TAG, "Decisive direct sweep complete at angle=%u deg",
             (unsigned)((position_mdeg + 500) / 1000));
  }
}

void servo_hold(void) {
  moving = false;

  target_mdeg = position_mdeg;

  ESP_LOGW(TAG, "Motion held at commanded angle=%u deg",
           (unsigned)((position_mdeg + 500U) / 1000U));
}

void servo_init(int servo_pin) {
  reject_angle = SERVO_DEFAULT_REJECT_DEG;
  speed_dps = SERVO_DEFAULT_SPEED_DPS;
  position_mdeg = target_mdeg = 0;
  moving = false;

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
           ", direct travel=%" PRIu32 " ms",
           SERVO_DUTY_HOME, reject_angle,
           duty_for_position((int32_t)reject_angle * 1000),
           servo_travel_ms());
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
