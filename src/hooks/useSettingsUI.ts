import { useReducer } from 'react';

type SettingsUIState = {
  purgeConfirm: boolean;
  isSaving: boolean;
};

type SettingsUIAction = 
  | { type: 'SET_PURGE_CONFIRM'; payload: boolean }
  | { type: 'SET_SAVING'; payload: boolean }
  | { type: 'TRIGGER_PURGE_SEQUENCE' };

const initialState: SettingsUIState = {
  purgeConfirm: false,
  isSaving: false,
};

function settingsReducer(state: SettingsUIState, action: SettingsUIAction): SettingsUIState {
  switch (action.type) {
    case 'SET_PURGE_CONFIRM':
      return { ...state, purgeConfirm: action.payload };
    case 'SET_SAVING':
      return { ...state, isSaving: action.payload };
    case 'TRIGGER_PURGE_SEQUENCE':
      return { ...state, purgeConfirm: true };
    default:
      return state;
  }
}

export function useSettingsUI() {
  const [state, dispatch] = useReducer(settingsReducer, initialState);

  const confirmPurge = () => {
    dispatch({ type: 'SET_PURGE_CONFIRM', payload: true });
    setTimeout(() => dispatch({ type: 'SET_PURGE_CONFIRM', payload: false }), 3000);
  };

  return { 
    uiState: state,
    dispatch,
    confirmPurge
  };
}
