# Transform received state into control outputs
def control(state: RobotState, control: RobotControl) -> RobotControl:

    THRESHOLD = 500

    control.effort.x = 1 if state.light_left > THRESHOLD else 0
    control.effort.y = -1 if state.light_right > THRESHOLD else 0
    
    return control
