#include "led.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_log.h"

static const char *TAG = "LED";

#define LEDC_TIMER              LEDC_TIMER_1
#define LEDC_MODE               LEDC_LOW_SPEED_MODE
#define LEDC_CHANNEL            LEDC_CHANNEL_1
#define LEDC_DUTY_RES           LEDC_TIMER_8_BIT // Set duty resolution to 8 bits
#define LEDC_FREQUENCY          5000 // Frequency in Hertz. Set frequency at 5 kHz

static int _in3, _in4, _enb;
static uint8_t requested_brightness;

void led_init(int in3_pin, int in4_pin, int enb_pin) {
    _in3 = in3_pin;
    _in4 = in4_pin;
    _enb = enb_pin;

    ESP_LOGI(TAG, "Initializing LED GPIOs and PWM (L298N Channel B)");

    // Configure IN3 and IN4 as outputs
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = (1ULL << _in3) | (1ULL << _in4),
        .pull_down_en = 0,
        .pull_up_en = 0
    };
    gpio_config(&io_conf);
    
    // Set IN3 HIGH and IN4 LOW for forward bias of the LED
    gpio_set_level(_in3, 1);
    gpio_set_level(_in4, 0);

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
        .gpio_num       = _enb, // Set the output GPIO
        .duty           = 0, // Set duty to 0% (off initially)
        .hpoint         = 0
    };
    ledc_channel_config(&ledc_channel);
}

void led_set_brightness(uint8_t brightness) {
    requested_brightness=brightness;
    ledc_set_duty(LEDC_MODE, LEDC_CHANNEL, brightness);
    ledc_update_duty(LEDC_MODE, LEDC_CHANNEL);
}

uint8_t led_brightness(void) { return requested_brightness; }
