#ifndef SENSOR_H
#define SENSOR_H

#include <stdbool.h>

// Initialize the sensors
void sensor_init(int camera_sensor_pin, int ir_sensor_pin);

// Returns true if camera sensor detects an object (LOW)
bool is_camera_sensor_triggered(void);

// Returns true if IR sensor detects an object (LOW)
bool is_ir_triggered(void);

#endif // SENSOR_H
