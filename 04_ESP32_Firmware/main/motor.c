#include "motor.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_log.h"

static const char *TAG = "MOTOR";

#define LEDC_TIMER              LEDC_TIMER_0
#define LEDC_MODE               LEDC_LOW_SPEED_MODE
#define LEDC_CHANNEL            LEDC_CHANNEL_0
#define LEDC_DUTY_RES           LEDC_TIMER_8_BIT // Set duty resolution to 8 bits (0-255)
#define LEDC_FREQUENCY          5000 // Frequency in Hertz. Set frequency at 5 kHz

static int _in1, _in2, _ena;
static uint8_t requested_speed=255;
static bool running=false;

void motor_init(int in1_pin, int in2_pin, int ena_pin) {
    _in1 = in1_pin;
    _in2 = in2_pin;
    _ena = ena_pin;

    ESP_LOGI(TAG, "Initializing Motor GPIOs and PWM");

    // Configure IN1 and IN2 as outputs
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = (1ULL << _in1) | (1ULL << _in2),
        .pull_down_en = 0,
        .pull_up_en = 0
    };
    gpio_config(&io_conf);
    
    // Ensure motor is stopped initially
    gpio_set_level(_in1, 0);
    gpio_set_level(_in2, 0);

    // Prepare and then apply the LEDC PWM timer configuration
    ledc_timer_config_t ledc_timer = {
        .speed_mode       = LEDC_MODE,
        .timer_num        = LEDC_TIMER,
        .duty_resolution  = LEDC_DUTY_RES,
        .freq_hz          = LEDC_FREQUENCY,
        .clk_cfg          = LEDC_AUTO_CLK
    };
    ledc_timer_config(&ledc_timer);

    // Prepare and then apply the LEDC PWM channel configuration
    ledc_channel_config_t ledc_channel = {
        .speed_mode     = LEDC_MODE,
        .channel        = LEDC_CHANNEL,
        .timer_sel      = LEDC_TIMER,
        .intr_type      = LEDC_INTR_DISABLE,
        .gpio_num       = _ena, // Set the output GPIO
        .duty           = 0, // Set duty to 0%
        .hpoint         = 0
    };
    ledc_channel_config(&ledc_channel);
}

void motor_set_speed(uint8_t speed) {
    requested_speed=speed;
    ledc_set_duty(LEDC_MODE, LEDC_CHANNEL, running ? speed : 0);
    ledc_update_duty(LEDC_MODE, LEDC_CHANNEL);
}

uint8_t motor_speed(void) { return requested_speed; }

void motor_start(void) {
    ESP_LOGI(TAG, "Starting motor");
    gpio_set_level(_in1, 1);
    gpio_set_level(_in2, 0);
    running=true;
    motor_set_speed(requested_speed);
}

void motor_stop(void) {
    ESP_LOGI(TAG, "Stopping motor");
    gpio_set_level(_in1, 0);
    gpio_set_level(_in2, 0);
    running=false;
    ledc_set_duty(LEDC_MODE, LEDC_CHANNEL, 0);
    ledc_update_duty(LEDC_MODE, LEDC_CHANNEL);
}
