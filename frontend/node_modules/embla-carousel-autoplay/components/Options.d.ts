import { CreateOptionsType, EmblaCarouselType } from 'embla-carousel';
export type DelayOptionType = number | ((scrollSnaps: number[], emblaApi: EmblaCarouselType) => number[]);
export type RootNodeType = null | ((emblaRoot: HTMLElement) => HTMLElement | null);
export type OptionsType = CreateOptionsType<{
    delay: DelayOptionType;
    instant: boolean;
    defaultInteraction: boolean;
    stopOnLastSnap: boolean;
    rootNode: RootNodeType;
}>;
export declare const defaultOptions: OptionsType;
