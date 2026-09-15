import { AnimationsRenderType, AnimationsUpdateType } from './Animations.js';
export type ScrollEventType = {
    isDragging: boolean;
};
export type ScrollAnimatorType = {
    update: AnimationsUpdateType;
    render: AnimationsRenderType;
};
export declare function ScrollAnimator(): ScrollAnimatorType;
