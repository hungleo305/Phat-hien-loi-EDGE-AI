#include "uart.h"
#include "protocol.h"
#include "driver/uart.h"
#include "esp_log.h"
#include <stdio.h>
#include <string.h>
#include <inttypes.h>

static int port;
static QueueHandle_t events;
static pi_line_t line;
void uart_pi_init(int tx_pin,int rx_pin,int port_num,int baud_rate) {
    port=port_num;
    uart_config_t config={.baud_rate=baud_rate,.data_bits=UART_DATA_8_BITS,
        .parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,
        .flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_param_config(port,&config));
    ESP_ERROR_CHECK(uart_set_pin(port,tx_pin,rx_pin,UART_PIN_NO_CHANGE,UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_driver_install(port,BUF_SIZE*2,0,16,&events,0));
}
bool uart_send_capture_command(uint32_t session,uint32_t box_id) {
    char command[80];
    int length=snprintf(command,sizeof(command),"CAPTURE %"PRIu32" %"PRIu32"\n",session,box_id);
    return uart_write_bytes(port,command,length)==length;
}
void uart_send_hello(uint32_t session) {
    char command[64]; int length=snprintf(command,sizeof(command),"HELLO %"PRIu32" 1\n",session);
    uart_write_bytes(port,command,length);
}
void uart_send_operator_ack(uint32_t session, uint32_t sequence, bool accepted) {
    char command[80];
    int length=snprintf(command,sizeof(command),"OPACK %"PRIu32" %"PRIu32" %s\n",
                        session,sequence,accepted?"OK":"DENY");
    uart_write_bytes(port,command,length);
}
void uart_send_state(uint32_t session, const char *state, bool motor, bool sorting,
                     bool ready, bool camera, bool gate, unsigned queue,
                     uint32_t latest_id, bool fault, unsigned motor_speed, unsigned light_level,
                     unsigned servo_angle, unsigned servo_speed, uint32_t servo_hold_requested,
                     uint32_t servo_hold_effective, bool servo_moving) {
    char command[192];
    int length=snprintf(command,sizeof(command),
        "STATE %"PRIu32" %s %u %u %u %u %u %u %"PRIu32" %u %u %u %u %u %"PRIu32" %"PRIu32" %u\n",
        session,state,motor,sorting,ready,camera,gate,queue,latest_id,fault,motor_speed,light_level,
        servo_angle,servo_speed,servo_hold_requested,servo_hold_effective,servo_moving);
    if(length>0 && length<(int)sizeof(command)) uart_write_bytes(port,command,length);
}
bool uart_read_message(char *buffer,int max_len) {
    uart_event_t event;
    while(xQueueReceive(events,&event,0)==pdTRUE) {
        if(event.type==UART_FIFO_OVF || event.type==UART_BUFFER_FULL ||
           event.type==UART_FRAME_ERR || event.type==UART_PARITY_ERR || event.type==UART_BREAK) {
            uart_flush_input(port); memset(&line,0,sizeof(line)); line.discard=true;
            ESP_LOGE("UART","RX error %d; discard through next newline",event.type);
        }
    }
    if(max_len<2) return false;
    unsigned char byte;
    for(int i=0;i<PI_LINE_SIZE;i++) {
        if(uart_read_bytes(port,&byte,1,0)!=1) break;
        if(pi_line_feed(&line,byte,buffer,(size_t)max_len)) return true;
    }
    return false;
}
