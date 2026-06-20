import time

# 1. Save the start time outside the periodic callback function
start_time = time.time()


def control(state: RobotState, control: RobotControl) -> RobotControl:
    global start_time

    # 2. Calculate the delta time (elapsed seconds since the program started)
    elapsed_time = time.time() - start_time

    # 3. Repeat a 2-second cycle indefinitely (1s forward + 1s turn)
    # cycle_time will always be a float looping between 0.000 and 1.999
    cycle_time = elapsed_time % 2.0

    if cycle_time < 1.0:
        # Phase 1: Drive forward (seconds 0.0 to 1.0)
        control.effort.x = 1   # Left motor forward
        control.effort.y = 1   # Right motor forward
    else:
        # Phase 2: Turn right in place (seconds 1.0 to 2.0)
        control.effort.x = 1   # Left motor forward
        control.effort.y = -1  # Right motor reverse

    return control