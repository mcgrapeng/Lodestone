import { EngineType } from './Engine.js';
import { WindowType } from './utils.js';
export type AnimationsUpdateType = (engine: EngineType) => void;
export type AnimationsRenderType = (engine: EngineType, alpha: number) => void;
export type AnimationsType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
    start: () => void;
    stop: () => void;
    update: () => void;
    render: (alpha: number) => void;
};
export declare function Animations(update: () => void, render: (alpha: number) => void): AnimationsType;
