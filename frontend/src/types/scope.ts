export type TriggerType = 'Rising Edge' | 'Falling Edge' | 'State High' | 'State Low' | 'None';

export interface ChannelConfig {
  key: string;             
  color: string;           
  visible: boolean;        
  focused: boolean;        
  
  y_offset: number;        
  y_scale: number;         
  grid_size: number;       
  
  trigger_type: TriggerType; 
  trigger_level: number;   
}

export type ScopeState = Record<string, ChannelConfig>;
