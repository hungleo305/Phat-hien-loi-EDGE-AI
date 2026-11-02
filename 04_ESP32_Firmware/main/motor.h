#ifndef MOTOR_H
#define MOTOR_H

#include <stdint.h>
#include <stdbool.h>

// Initialize the motor driver pins and PWM
void motor_init(int in1_pin, int in2_pin, int ena_pin);

// Start the motor (forward direction)
void motor_start(void);

// Stop the motor
void motor_stop(void);

// Set motor speed (0-255)
void motor_set_speed(uint8_t speed);
uint8_t motor_speed(void);

#endif // MOTOR_H
