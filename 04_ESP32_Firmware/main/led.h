#ifndef LED_H
#define LED_H

#include <stdint.h>

// Initialize the LED driver pins and PWM
void led_init(int in3_pin, int in4_pin, int enb_pin);

// Set LED brightness (0-255). 0 is off, 255 is fully on.
void led_set_brightness(uint8_t brightness);
uint8_t led_brightness(void);

#endif // LED_H
