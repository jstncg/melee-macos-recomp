// gcshim -- presents phone input to Melee as four GameCube controllers.
//
// Loaded via DYLD_INSERT_LIBRARIES into MeleeRuntime, which statically links
// SDL3 and exports the virtual-joystick API. We resolve those symbols with
// dlsym(RTLD_DEFAULT) rather than linking SDL, so this builds against nothing
// and cannot drift out of sync with the runtime's SDL version.
//
// Injection works because the app is ad-hoc signed WITHOUT hardened runtime
// (codesign reports flags=0x2). If a future build enables hardened runtime,
// this stops loading and the fallback is patching the runtime source instead.
//
// Wire format is phonepad's 27-byte packet, little-endian:
//   uint8 port, float mainX, mainY, cX, cY, L, R, uint16 buttons

#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <math.h>
#include <sys/time.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define PORTS 4
#define UDP_PORT 41234
#define PACKET_BYTES 27

// ---- SDL3 types we need, mirrored from SDL_joystick.h (SDL 3.4.x) ----

typedef struct SDL_Joystick SDL_Joystick;
typedef uint32_t SDL_JoystickID;

typedef struct {
    uint32_t version;
    uint16_t type, padding, vendor_id, product_id;
    uint16_t naxes, nbuttons, nballs, nhats, ntouchpads, nsensors;
    uint16_t padding2[2];
    uint32_t button_mask, axis_mask;
    const char* name;
    const void* touchpads;
    const void* sensors;
    void* userdata;
    void (*Update)(void*);
    void (*SetPlayerIndex)(void*, int);
    bool (*Rumble)(void*, uint16_t, uint16_t);
    bool (*RumbleTriggers)(void*, uint16_t, uint16_t);
    bool (*SetLED)(void*, uint8_t, uint8_t, uint8_t);
    bool (*SendEffect)(void*, const void*, int);
    bool (*SetSensorsEnabled)(void*, bool);
    void (*Cleanup)(void*);
} SDL_VirtualJoystickDesc;

// SDL_INIT_INTERFACE() sets version = sizeof(*iface), not a constant. Passing
// anything else makes SDL_AttachVirtualJoystick reject the descriptor.
#define SDL_JOYSTICK_TYPE_GAMEPAD 1
#define SDL_INIT_JOYSTICK 0x00000200u

// SDL_GamepadAxis / SDL_GamepadButton ordinals.
enum { AX_LX, AX_LY, AX_RX, AX_RY, AX_LT, AX_RT, AX_COUNT };
enum { BTN_SOUTH, BTN_EAST, BTN_WEST, BTN_NORTH, BTN_BACK, BTN_GUIDE,
       BTN_START, BTN_LSTICK, BTN_RSTICK, BTN_LSHOULDER, BTN_RSHOULDER,
       BTN_DUP, BTN_DDOWN, BTN_DLEFT, BTN_DRIGHT, MY_NBUTTONS };

// ---- resolved at load ----

static SDL_JoystickID (*p_attach)(const SDL_VirtualJoystickDesc*);
static SDL_Joystick*  (*p_open)(SDL_JoystickID);
static bool (*p_set_axis)(SDL_Joystick*, int, int16_t);
static bool (*p_set_button)(SDL_Joystick*, int, bool);
static uint32_t (*p_was_init)(uint32_t);
static const char* (*p_get_error)(void);
// Enumeration, purely so we can log what Dolphin will actually see. Dolphin
// names an SDL device with SDL_GetGamepadName(), which for a virtual joystick
// comes from SDL's generated mapping -- not necessarily the name we passed in.
static SDL_JoystickID* (*p_get_joysticks)(int*);
static const char* (*p_joy_name_for_id)(SDL_JoystickID);
static const char* (*p_pad_name_for_id)(SDL_JoystickID);
static bool (*p_is_gamepad)(SDL_JoystickID);

static SDL_Joystick* pads[PORTS];

// SDL_SetJoystickVirtualButton() takes a PHYSICAL button index, not a gamepad
// ordinal. For a gamepad-typed virtual joystick, SDL walks the gamepad button
// enum in order and hands out physical indices only for bits set in
// button_mask (see SDL_virtualjoystick.c, current_button++). So we must
// translate. Getting this wrong made A/B/X/Y work by coincidence -- their
// ordinals happen to be 0-3 -- while Start pressed D-pad Up and Z fell off
// the end of the device entirely.
static int phys_of[MY_NBUTTONS];

// Per-port receipt counters. Without these there is no way to tell "this
// player's packets never reach the game" apart from "this player is pressing
// the wrong button".
static unsigned long rx_count[PORTS];

// phonepad button bits -> SDL gamepad buttons. Melee's GC layout:
// A=attack, B=special, X=jump, Z=grab, Start=pause.
static const struct { uint16_t bit; int sdl; } BUTTON_MAP[] = {
    { 1,  BTN_SOUTH     },  // A
    { 2,  BTN_EAST      },  // B
    { 4,  BTN_WEST      },  // X
    { 8,  BTN_NORTH     },  // Y
    { 16, BTN_RSHOULDER },  // Z
    { 32, BTN_START     },  // Start
    { 64, BTN_DUP       },
    { 128, BTN_DDOWN    },
    { 256, BTN_DLEFT    },
    { 512, BTN_DRIGHT   },
};
#define BUTTON_MAP_N (sizeof BUTTON_MAP / sizeof BUTTON_MAP[0])

// The runtime swallows stderr, so log to a file we control. Override the
// path with GCSHIM_LOG if you want it somewhere else.
static void log_line(const char* msg) {
    const char* path = getenv("GCSHIM_LOG");
    if (!path) path = "/tmp/gcshim.log";
    FILE* f = fopen(path, "a");
    if (!f) return;
    fprintf(f, "[gcshim] %s\n", msg);
    fclose(f);
}

static int16_t bipolar(float v) {
    if (!isfinite(v)) return 0;
    if (v < -1.0f) v = -1.0f;
    if (v >  1.0f) v =  1.0f;
    // 32767 both ways: a GC stick is symmetric, and -32768 would clip asymmetrically.
    return (int16_t) (v * 32767.0f);
}

// Trigger axes are bipolar, NOT 0..max. SDL parks them at
// SDL_JOYSTICK_AXIS_MIN at rest (SDL_virtualjoystick.c: "Trigger axes are at
// minimum value at rest") and maps -32768..32767 onto 0..1. Sending 0 for
// "released" therefore reads as a half-pressed trigger -- which in Melee is
// a permanently held shield.
static int16_t trigger(float v) {
    if (!isfinite(v)) return -32768;
    if (v <= 0.0f) return -32768;
    if (v >= 1.0f) return 32767;
    return (int16_t) (v * 65535.0f - 32768.0f);
}

static bool resolve(void) {
    p_attach     = dlsym(RTLD_DEFAULT, "SDL_AttachVirtualJoystick");
    p_open       = dlsym(RTLD_DEFAULT, "SDL_OpenJoystick");
    p_set_axis   = dlsym(RTLD_DEFAULT, "SDL_SetJoystickVirtualAxis");
    p_set_button = dlsym(RTLD_DEFAULT, "SDL_SetJoystickVirtualButton");
    p_was_init   = dlsym(RTLD_DEFAULT, "SDL_WasInit");
    p_get_error  = dlsym(RTLD_DEFAULT, "SDL_GetError");
    p_get_joysticks   = dlsym(RTLD_DEFAULT, "SDL_GetJoysticks");
    p_joy_name_for_id = dlsym(RTLD_DEFAULT, "SDL_GetJoystickNameForID");
    p_pad_name_for_id = dlsym(RTLD_DEFAULT, "SDL_GetGamepadNameForID");
    p_is_gamepad      = dlsym(RTLD_DEFAULT, "SDL_IsGamepad");
    return p_attach && p_open && p_set_axis && p_set_button && p_was_init;
}

static bool attach_pad(int port) {
    static const char* names[PORTS] = {
        "Phone GC Port 1", "Phone GC Port 2", "Phone GC Port 3", "Phone GC Port 4",
    };

    SDL_VirtualJoystickDesc desc;
    memset(&desc, 0, sizeof desc);
    desc.version    = (uint32_t) sizeof desc;
    desc.type       = SDL_JOYSTICK_TYPE_GAMEPAD;
    desc.vendor_id  = 0x057E;  // Nintendo, so the runtime's heuristics treat it sanely
    // Distinct product per port. All four sharing one product id made SDL
    // generate a single gamepad mapping and report its name for every pad, so
    // Dolphin saw four identically-named devices and numbered them 0-3.
    desc.product_id = (uint16_t) (0x0340 + port);
    desc.naxes      = AX_COUNT;
    desc.nbuttons   = MY_NBUTTONS;  // our device's count, not SDL_GAMEPAD_BUTTON_COUNT
    desc.name       = names[port];
    desc.button_mask = 0;
    for (size_t i = 0; i < BUTTON_MAP_N; i++) desc.button_mask |= 1u << BUTTON_MAP[i].sdl;
    desc.axis_mask = (1u << AX_LX) | (1u << AX_LY) | (1u << AX_RX)
                   | (1u << AX_RY) | (1u << AX_LT) | (1u << AX_RT);

    // Same walk SDL performs, over the same mask, so the indices agree.
    int next_physical = 0;
    for (int gb = 0; gb < MY_NBUTTONS; gb++)
        phys_of[gb] = (desc.button_mask & (1u << gb)) ? next_physical++ : -1;

    SDL_JoystickID id = p_attach(&desc);
    if (id == 0) {
        char buf[256];
        snprintf(buf, sizeof buf, "attach port %d failed: %s",
                 port + 1, p_get_error ? p_get_error() : "?");
        log_line(buf);
        return false;
    }
    pads[port] = p_open(id);
    return pads[port] != NULL;
}

static void apply(int port, const float a[6], uint16_t buttons) {
    SDL_Joystick* j = pads[port];
    if (!j) return;

    p_set_axis(j, AX_LX, bipolar(a[0]));
    // Phone sends GC convention (up positive); SDL's Y grows downward.
    p_set_axis(j, AX_LY, bipolar(-a[1]));
    p_set_axis(j, AX_RX, bipolar(a[2]));
    p_set_axis(j, AX_RY, bipolar(-a[3]));
    p_set_axis(j, AX_LT, trigger(a[4]));
    p_set_axis(j, AX_RT, trigger(a[5]));

    for (size_t i = 0; i < BUTTON_MAP_N; i++) {
        int phys = phys_of[BUTTON_MAP[i].sdl];
        if (phys >= 0)
            p_set_button(j, phys, (buttons & BUTTON_MAP[i].bit) != 0);
    }
}

static double now_seconds(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return now.tv_sec + now.tv_nsec / 1e9;
}

static void* run(void* unused) {
    (void) unused;

    log_line("loaded; resolving SDL symbols");
    if (!resolve()) { log_line("SDL virtual-joystick symbols not found; giving up"); return NULL; }
    log_line("symbols resolved; waiting for SDL_INIT_JOYSTICK");

    // Attaching before SDL_Init(JOYSTICK) fails, and the runtime initialises
    // SDL well after our constructor runs. Wait for it.
    int waited = 0;
    for (; waited < 600 && !(p_was_init(SDL_INIT_JOYSTICK) & SDL_INIT_JOYSTICK); waited++) {
        usleep(100 * 1000);
        if (waited && waited % 50 == 0) {
            char w[96];
            snprintf(w, sizeof w, "still waiting for SDL joystick init (%ds)", waited / 10);
            log_line(w);
        }
    }
    if (!(p_was_init(SDL_INIT_JOYSTICK) & SDL_INIT_JOYSTICK)) {
        log_line("SDL joystick subsystem never came up after 60s; giving up");
        return NULL;
    }

    int attached = 0;
    for (int port = 0; port < PORTS; port++) if (attach_pad(port)) attached++;
    char buf[64];
    snprintf(buf, sizeof buf, "attached %d/%d virtual GameCube pads", attached, PORTS);
    log_line(buf);
    if (attached == 0) return NULL;

    // Log the exact identity of every joystick SDL knows about. This is the
    // string Dolphin's GCPadNew.ini "Device = SDL/<id>/<name>" must match.
    if (p_get_joysticks && p_joy_name_for_id) {
        int n = 0;
        SDL_JoystickID* ids = p_get_joysticks(&n);
        snprintf(buf, sizeof buf, "SDL sees %d joystick(s):", n);
        log_line(buf);
        for (int i = 0; i < n; i++) {
            const char* jn = p_joy_name_for_id(ids[i]);
            bool isgp = p_is_gamepad ? p_is_gamepad(ids[i]) : false;
            const char* gn = (isgp && p_pad_name_for_id) ? p_pad_name_for_id(ids[i]) : NULL;
            char line[256];
            snprintf(line, sizeof line,
                     "  instance=%u gamepad=%s joystick_name=\"%s\" gamepad_name=\"%s\"",
                     (unsigned) ids[i], isgp ? "yes" : "NO",
                     jn ? jn : "(null)", gn ? gn : "(null)");
            log_line(line);
        }
    }

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { log_line("socket() failed"); return NULL; }
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    int udp_port = UDP_PORT;
    const char* value = getenv("GCSHIM_UDP_PORT");
    if (value) {
        char* end = NULL;
        long parsed = strtol(value, &end, 10);
        if (!*value || *end || parsed < 1 || parsed > 65535) {
            log_line("invalid GCSHIM_UDP_PORT"); close(fd); return NULL;
        }
        udp_port = (int)parsed;
    }
    addr.sin_port = htons((uint16_t)udp_port);
    if (bind(fd, (struct sockaddr*) &addr, sizeof addr) < 0) {
        log_line("controller UDP port is busy; choose another --udp-port");
        close(fd);
        return NULL;
    }
    snprintf(buf, sizeof buf, "listening on udp 127.0.0.1:%d", udp_port);
    log_line(buf);

    struct timeval timeout = { .tv_sec = 0, .tv_usec = 100000 };
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout) < 0) {
        log_line("could not configure input watchdog"); close(fd); return NULL;
    }
    double last_input[PORTS] = {0};
    const float neutral_axes[6] = {0};
    for (int i = 0; i < PORTS; i++) apply(i, neutral_axes, 0);
    uint8_t pkt[64];
    unsigned long reported[PORTS] = {0};
    time_t next_report = time(NULL) + 5;

    for (;;) {
        ssize_t n = recv(fd, pkt, sizeof pkt, 0);
        double received_at = now_seconds();
        for (int i = 0; i < PORTS; i++) {
            if (last_input[i] && received_at - last_input[i] > 1.0) {
                apply(i, neutral_axes, 0);
                last_input[i] = 0;
                char line[96];
                snprintf(line, sizeof line, "stale phone %d; controls released", i + 1);
                log_line(line);
            }
        }
        if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) {
            log_line("controller socket failed"); close(fd); return NULL;
        }
        if (n != PACKET_BYTES) continue;  // ignore anything that isn't ours

        uint8_t port = pkt[0];
        if (port >= PORTS) continue;

        float a[6];
        memcpy(a, pkt + 1, sizeof a);
        uint16_t buttons;
        memcpy(&buttons, pkt + 25, sizeof buttons);

        last_input[port] = received_at;
        rx_count[port]++;
        apply(port, a, buttons);

        // Report only when a count actually moved, so an idle session stays quiet.
        time_t now = time(NULL);
        if (now >= next_report) {
            next_report = now + 5;
            bool changed = false;
            for (int i = 0; i < PORTS; i++)
                if (rx_count[i] != reported[i]) changed = true;
            if (changed) {
                char line[160];
                int n = snprintf(line, sizeof line, "packets:");
                for (int i = 0; i < PORTS; i++) {
                    n += snprintf(line + n, sizeof line - n, " P%d=%lu", i + 1, rx_count[i]);
                    reported[i] = rx_count[i];
                }
                log_line(line);
            }
        }
    }
}

__attribute__((constructor))
static void gcshim_init(void) {
    pthread_t t;
    if (pthread_create(&t, NULL, run, NULL) == 0) pthread_detach(t);
    else log_line("pthread_create failed");
}
