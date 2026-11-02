#ifndef SERVO_H
#define SERVO_H

#include <stdbool.h>
#include <stdint.h>

// Initialize the servo PWM
void servo_init(int servo_pin);

// Park the arm parallel to the belt (0-degree reference after horn setup).
void servo_reset(void);

// Move the arm to the calibrated diagonal reject position.
void servo_reject(void);

// Calibration is volatile and is allowed only while STOPPED by the caller.
bool servo_set_reject_angle(unsigned angle);
bool servo_preview_angle(unsigned angle);
unsigned servo_reject_angle(void);
unsigned servo_current_angle(void);
/* Nonblocking soft motion, serviced by the single control task. These are
   commanded positions, not feedback from a physical angle/torque sensor. */
void servo_service(uint64_t now_ms);
void servo_hold(void);
bool servo_is_moving(void);
bool servo_set_speed(unsigned degrees_per_second);
unsigned servo_speed(void);
uint32_t servo_travel_ms(void);

#endif // SERVO_H
