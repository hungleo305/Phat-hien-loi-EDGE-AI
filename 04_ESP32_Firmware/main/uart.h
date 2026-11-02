#ifndef UART_H
#define UART_H

#include <stdbool.h>
#include <stdint.h>

#define BUF_SIZE 1024

// Initialize UART communication
void uart_pi_init(int tx_pin, int rx_pin, int port_num, int baud_rate);

// Send the "CAPTURE" command to Raspberry Pi
bool uart_send_capture_command(uint32_t session, uint32_t box_id);
void uart_send_hello(uint32_t session);
void uart_send_operator_ack(uint32_t session, uint32_t sequence, bool accepted);
void uart_send_state(uint32_t session, const char *state, bool motor, bool sorting,
                     bool ready, bool camera, bool gate, unsigned queue,
                     uint32_t latest_id, bool fault, unsigned motor_speed, unsigned light_level,
                     unsigned servo_angle, unsigned servo_speed, uint32_t servo_hold_requested,
                     uint32_t servo_hold_effective, bool servo_moving);

// Check if there is data available and read it
// Returns true if a complete message was received
bool uart_read_message(char* buffer, int max_len);

#endif // UART_H
