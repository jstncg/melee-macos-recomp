// Local development app launcher; game code executes in the ARM64 runtime.
#include <mach-o/dyld.h>
#include <limits.h>
#include <libgen.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

int main(void) {
    char executable[PATH_MAX], canonical[PATH_MAX], script[PATH_MAX], logfile[PATH_MAX];
    uint32_t size = sizeof executable;
    if (_NSGetExecutablePath(executable, &size) || !realpath(executable, canonical))
        return 1;
    char runtime[PATH_MAX];
    snprintf(runtime, sizeof runtime, "%s", canonical);
    char *filename = strrchr(runtime, '/');
    if (!filename) return 1;
    *filename = '\0';
    size_t used = strlen(runtime);
    if (used + strlen("/MeleeRuntime") + 1 > sizeof runtime) return 1;
    strcat(runtime, "/MeleeRuntime");
    setenv("MELEE_RUNNER_PATH", runtime, 1);
    // <workspace>/Melee macOS.app/Contents/MacOS/Melee
    for (int i = 0; i < 4; ++i) {
        char *slash = strrchr(canonical, '/');
        if (!slash) return 1;
        *slash = '\0';
    }
    setenv("MELEE_WORKSPACE", canonical, 1);
    setenv("MELEE_FRONTEND", "1", 1);
    if (snprintf(script, sizeof script, "%s/scripts/run_macos.sh", canonical) >= sizeof script)
        return 1;
    if (snprintf(logfile, sizeof logfile, "%s/logs/app.log", canonical) >= sizeof logfile)
        return 1;
    int fd = open(logfile, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd >= 0) { dup2(fd, STDOUT_FILENO); dup2(fd, STDERR_FILENO); close(fd); }
    char *args[] = {"/bin/bash", script, NULL};
    execv(args[0], args);
    perror("Melee launch failed");
    return 1;
}
