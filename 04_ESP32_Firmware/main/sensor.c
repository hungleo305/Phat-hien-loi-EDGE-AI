#include "sensor.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_log.h"

static const char *TAG = "SENSOR";

static int _camera_pin, _ir_pin;

void sensor_init(int camera_sensor_pin, int ir_sensor_pin) {
    _camera_pin = camera_sensor_pin;
    _ir_pin = ir_sensor_pin;
    ESP_LOGI(TAG, "Initializing Sensors");

    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = (1ULL << _camera_pin) | (1ULL << _ir_pin),
        .pull_down_en = 0,
        .pull_up_en = 1 // Enable internal pull-up resistor
    };
    ESP_ERROR_CHECK(gpio_config(&io_conf));
    ESP_LOGI(TAG, "Inputs ready: camera_gpio=%d level=%d gate_gpio=%d level=%d",
             _camera_pin, gpio_get_level(_camera_pin),
             _ir_pin, gpio_get_level(_ir_pin));
}

bool is_camera_sensor_triggered(void) {
    // Sensor normally outputs HIGH, and pulls LOW when object is detected
    return (gpio_get_level(_camera_pin) == 0);
}

bool is_ir_triggered(void) {
    // LM393 typically outputs LOW (0) when object is detected
    return (gpio_get_level(_ir_pin) == 0);
}
