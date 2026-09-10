import { AlignmentOptionType } from './Alignment.js';
import { AxisDirectionOptionType, AxisOptionType } from './Axis.js';
import { SlidesToScrollOptionType } from './SlidesToScroll.js';
import { ScrollContainOptionType } from './ScrollContain.js';
import { SlidesInViewMarginOptionsType, SlidesInViewThresholdOptionsType } from './SlidesInView.js';
export type LooseOptionsType = {
    [key: string]: unknown;
};
export type CreateOptionsType<Type extends LooseOptionsType> = Type & {
    active: boolean;
    breakpoints: {
        [key: string]: Omit<Partial<CreateOptionsType<Type>>, 'breakpoints'>;
    };
};
export type OptionsType = CreateOptionsType<{
    align: AlignmentOptionType;
    axis: AxisOptionType;
    container: string | HTMLElement | null;
    slides: string | HTMLElement[] | NodeListOf<HTMLElement> | null;
    containScroll: ScrollContainOptionType;
    direction: AxisDirectionOptionType;
    slidesToScroll: SlidesToScrollOptionType;
    dragFree: boolean;
    dragThreshold: number;
    inViewThreshold: SlidesInViewThresholdOptionsType;
    inViewMargin: SlidesInViewMarginOptionsType;
    loop: boolean;
    skipSnaps: boolean;
    duration: number;
    startSnap: number;
    draggable: boolean;
    resize: boolean;
    focus: boolean;
    slideChanges: boolean;
}>;
export declare const defaultOptions: OptionsType;
export type EmblaOptionsType = Partial<OptionsType>;
