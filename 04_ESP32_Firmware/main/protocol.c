#include "protocol.h"
#include <string.h>

bool pi_line_feed(pi_line_t *line, unsigned char byte, char *out, size_t capacity) {
    if(byte=='\n') {
        bool valid=!line->discard && line->used>0 && line->used<capacity;
        if(valid) { memcpy(out,line->data,line->used); out[line->used]='\0'; }
        line->used=0; line->discard=false; line->cr=false; return valid;
    }
    if(byte=='\r') { if(line->cr) line->discard=true; line->cr=true; return false; }
    if(line->cr) { line->discard=true; return false; }
    if(byte<32 || byte>126 || line->used>=sizeof(line->data)-1) { line->discard=true; return false; }
    if(!line->discard) line->data[line->used++]=(char)byte;
    return false;
}
static bool number(const char **cursor, uint32_t *out) {
    const char *p=*cursor; uint32_t n=0;
    if(*p<'0'||*p>'9') return false;
    do {
        unsigned digit=(unsigned)(*p-'0');
        if(n>(UINT32_MAX-digit)/10) return false;
        n=n*10+digit; p++;
    } while(*p>='0'&&*p<='9');
    *cursor=p; *out=n; return true;
}
bool pi_parse(const char *line, pi_message_t *message) {
    memset(message,0,sizeof(*message)); const char *p=line;
    if(strncmp(p,"READY ",6)==0) {
        p+=6;
        if(!number(&p,&message->session)||*p) return false;
        message->type=PI_READY; return true;
    }
    if(strncmp(p,"CAPTURED ",9)==0) {
        p+=9;
        if(!number(&p,&message->session)||*p++!=' ') return false;
        if(!number(&p,&message->id)||*p) return false;
        message->type=PI_CAPTURED;return true;
    }
    if(strncmp(p,"RESULT ",7)!=0) return false;
    p+=7;
    if(!number(&p,&message->session)||*p++!=' ') return false;
    if(!number(&p,&message->id)||*p++!=' ') return false;
    if(strcmp(p,"PASS")==0) message->result=SG_PASS;
    else if(strcmp(p,"DEFECT")==0) message->result=SG_DEFECT;
    else if(strcmp(p,"ERROR")==0) message->result=SG_ERROR;
    else return false;
    message->type=PI_RESULT; return true;
}

bool pi_parse_operator(const char *line, op_message_t *message) {
    memset(message,0,sizeof(*message));
    if(strncmp(line,"OP ",3)!=0) return false;
    const char *p=line+3;
    if(!number(&p,&message->session)||*p++!=' ') return false;
    if(!number(&p,&message->sequence)||!message->sequence||*p++!=' ') return false;
    if(strcmp(p,"STOP")==0) message->verb=OP_STOP;
    else if(strcmp(p,"START")==0) message->verb=OP_START;
    else if(strcmp(p,"DRY")==0) message->verb=OP_DRY;
    else if(strcmp(p,"SORT")==0) message->verb=OP_SORT;
    else if(strcmp(p,"STATUS")==0) message->verb=OP_STATUS;
    else if(strncmp(p,"SPEED ",6)==0) {
        p+=6;
        if(!number(&p,&message->value)||*p||message->value<1||message->value>255) return false;
        message->verb=OP_SPEED;
    } else if(strncmp(p,"LIGHT ",6)==0) {
        p+=6;
        if(!number(&p,&message->value)||*p||message->value>255) return false;
        message->verb=OP_LIGHT;
    } else if(strncmp(p,"SERVO_ANGLE ",12)==0) {
        p+=12;
        if(!number(&p,&message->value)||*p||message->value<1||message->value>90) return false;
        message->verb=OP_SERVO_ANGLE;
    } else if(strncmp(p,"SERVO_SPEED ",12)==0) {
        p+=12;
        if(!number(&p,&message->value)||*p||message->value<30||message->value>240) return false;
        message->verb=OP_SERVO_SPEED;
    } else if(strncmp(p,"SERVO_HOLD ",11)==0) {
        p+=11;
        if(!number(&p,&message->value)||*p||message->value<150||message->value>1500) return false;
        message->verb=OP_SERVO_HOLD;
    } else return false;
    return true;
}

bool pi_parse_ping(const char *line, uint32_t *session) {
    if(strncmp(line,"PING ",5)!=0) return false;
    const char *p=line+5;
    return number(&p,session) && *p=='\0';
}
