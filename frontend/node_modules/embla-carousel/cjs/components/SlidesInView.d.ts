import { EventHandlerType } from './EventHandler';
import { WindowType } from './utils';
export type SlidesInViewThresholdOptionsType = IntersectionObserverInit['threshold'];
export type SlidesInViewMarginOptionsType = IntersectionObserverInit['rootMargin'];
export type SlidesInViewEventType = {
    slidesInView: number[];
    slidesLeftView: number[];
    slidesEnterView: number[];
};
export type SlidesInViewType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
    get: () => number[];
};
export declare function SlidesInView(container: HTMLElement, slides: HTMLElement[], eventHandler: EventHandlerType, threshold: SlidesInViewThresholdOptionsType, rootMargin: SlidesInViewMarginOptionsType): SlidesInViewType;
