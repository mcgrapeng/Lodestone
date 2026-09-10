import { EmblaCarouselType } from './EmblaCarousel.js';
import { PointerEventType } from './DragTracker.js';
import { SelectEventType } from './ScrollTo.js';
import { ScrollEventType } from './ScrollAnimator.js';
import { SlidesInViewEventType } from './SlidesInView.js';
export type EmblaEventType = keyof EmblaEventListType;
export type EmblaEventModelType<EventType extends keyof EmblaEventListType> = {
    api: EmblaCarouselType;
    type: EmblaEventType;
    detail: EmblaEventListType[EventType];
};
export type EmblaCreatedEventType = {
    api: EmblaCarouselType;
    emit: () => boolean;
};
export type EmblaEventCallbackType<EventType extends keyof EmblaEventListType> = (api: EmblaCarouselType, event: EmblaEventModelType<EventType>) => boolean | void;
export interface EmblaEventListType {
    pointerdown: PointerEventType;
    pointermove: PointerEventType;
    pointerup: PointerEventType;
    slideschanged: MutationRecord[];
    slidesinview: SlidesInViewEventType;
    select: SelectEventType;
    scroll: ScrollEventType;
    settle: null;
    destroy: null;
    reinit: null;
    resize: ResizeObserverEntry[];
    slidefocus: FocusEvent;
}
export type EventHandlerType = {
    init: (emblaApi: EmblaCarouselType) => void;
    clear: () => void;
    createEvent: <EventType extends keyof EmblaEventListType>(type: EventType, detail: EmblaEventListType[EventType]) => EmblaCreatedEventType;
    on<EventType extends keyof EmblaEventListType>(type: EventType, callback: EmblaEventCallbackType<EventType>): EventHandlerType;
    off<EventType extends keyof EmblaEventListType>(type: EventType, callback: EmblaEventCallbackType<EventType>): EventHandlerType;
};
export declare function EventHandler(): EventHandlerType;
