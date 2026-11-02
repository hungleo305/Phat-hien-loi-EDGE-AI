#ifndef PI_PROTOCOL_H
#define PI_PROTOCOL_H
#include "stopgo.h"
#include <stddef.h>
#define PI_LINE_SIZE 128
typedef enum { PI_INVALID, PI_READY, PI_RESULT, PI_CAPTURED } pi_message_type_t;
typedef struct { pi_message_type_t type; uint32_t session, id; sg_result_t result; } pi_message_t;
typedef enum { OP_STOP, OP_START, OP_DRY, OP_SORT, OP_STATUS, OP_SPEED, OP_LIGHT,
               OP_SERVO_ANGLE, OP_SERVO_SPEED, OP_SERVO_HOLD } op_verb_t;
typedef struct { uint32_t session, sequence, value; op_verb_t verb; } op_message_t;
typedef struct { char data[PI_LINE_SIZE]; size_t used; bool discard, cr; } pi_line_t;
/* Returns one complete nonempty LF-terminated line. CRLF is accepted. */
bool pi_line_feed(pi_line_t *line, unsigned char byte, char *out, size_t capacity);
bool pi_parse(const char *line, pi_message_t *message);
bool pi_parse_operator(const char *line, op_message_t *message);
bool pi_parse_ping(const char *line, uint32_t *session);
#endif
