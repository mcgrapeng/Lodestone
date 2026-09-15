import { AlignmentOptionType } from './Alignment';
import { AxisDirectionOptionType, AxisOptionType } from './Axis';
import { SlidesToScrollOptionType } from './SlidesToScroll';
import { ScrollContainOptionType } from './ScrollContain';
import { SlidesInViewMarginOptionsType, SlidesInViewThresholdOptionsType } from './SlidesInView';
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
