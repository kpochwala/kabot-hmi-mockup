def left(ctl):
    ctl.effort.x = 0.0
    ctl.effort.y = 1.0
    return ctl

def right(ctl):
    ctl.effort.x = 1.0
    ctl.effort.y = 0.0
    return ctl

def forward(ctl):
    ctl.effort.x = 1.0
    ctl.effort.y = 1.0
    return ctl

def stop(ctl):
    ctl.effort.x = 0.0
    ctl.effort.y = 0.0
    return ctl

# Transform received state into control outputs
def control(state: RobotState, control: RobotControl) -> RobotControl:

    DARK_THRESHOLD = 200
    FORWARD_THRESHOLD = 200

    diff = state.light_left - state.light_right
    avg = 0.5 * (state.light_left + state.light_right)
    
    print(f"diff: {diff}, avg: {avg}")

    # when it is already dark, stop moving
    if avg < 200:
        print("It is nicely dark in here.")
        return stop(control)
    
    # it is not dark, so consider where to go
    if abs(diff) < avg:
        return forward(control)
    
    if diff < 0:
        return left(control)

    if diff > 0:
        return right(control)

