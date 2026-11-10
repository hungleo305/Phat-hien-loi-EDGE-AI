#ifndef APP_CONFIG_H
#define APP_CONFIG_H
/* Existing ESP32 WROOM wiring. UART uses 3.3 V TTL, common GND. */
#define MOTOR_IN1_PIN 27
#define MOTOR_IN2_PIN 26
#define MOTOR_ENA_PIN 14
#define LED_IN3_PIN 32
#define LED_IN4_PIN 33
#define LED_ENB_PIN 25
#define SERVO_PIN 13
/* 0 deg parks the paddle parallel to the belt. 35 deg diagonal reject position. */
#define SERVO_DEFAULT_REJECT_DEG 35
#define SERVO_MAX_TEST_DEG 90
/* 1 when servo mechanical mounting orientation is reversed: duty decreases from neutral (1.5ms) */
#define SERVO_REVERSE_DIRECTION 1
/* Commanded angular speed ceiling. Default 230 dps gives 50 ms per step (150 ms total travel). */
#define SERVO_DEFAULT_SPEED_DPS 230
#define SERVO_MIN_SPEED_DPS 30
#define SERVO_MAX_SPEED_DPS 240
#define SERVO_ENDPOINT_ALLOWANCE_MS 50
#define CAMERA_SENSOR_PIN 18
#define IR_SENSOR_PIN 19
#define UART_TX_PIN 17
#define UART_RX_PIN 16
#define UART_PORT_NUM 2
#define UART_BAUD_RATE 115200
#define SENSOR_DEBOUNCE_MS 30
#define BOX_SETTLE_MS 250
#define PI_RESULT_TIMEOUT_MS 5000
#define PI_CAPTURE_TIMEOUT_MS 2000
#define GATE_TRANSIT_TIMEOUT_MS 15000
/* Active paddle: start OUT immediately at IR.
   IR is 13 cm from the shaft, alongside the parked paddle. */
#define SERVO_REJECT_MS 350
#define SERVO_OUT_MIN_MS 150
#define SERVO_OUT_MAX_MS 1500
#define SERVO_RETURN_MS 300
#define INITIAL_MOTOR_SPEED 160
#define INITIAL_LED_BRIGHTNESS 30
#endif
