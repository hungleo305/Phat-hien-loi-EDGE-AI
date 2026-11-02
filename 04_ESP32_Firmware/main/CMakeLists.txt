idf_component_register(SRCS "ESP32_Firmware.c" "motor.c" "led.c" "servo.c" "sensor.c" "uart.c" "stopgo.c" "protocol.c"
                    INCLUDE_DIRS "."
                    REQUIRES driver esp_timer esp_system)
