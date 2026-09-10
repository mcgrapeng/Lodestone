import { LimitType } from './Limit';
import { ScrollContainOptionType } from './ScrollContain';
import { ScrollProgressType } from './ScrollProgress';
import { SlidesToScrollType } from './SlidesToScroll';
type SnapBySlideType = {
    [key: number]: number;
};
export type ScrollSnapListType = {
    slidesBySnap: number[][];
    snapBySlide: SnapBySlideType;
    progressBySnap: number[];
    length: number;
};
export declare function ScrollSnapList(containSnaps: boolean, containScroll: ScrollContainOptionType, scrollSnaps: number[], scrollContainLimit: LimitType, slidesToScroll: SlidesToScrollType, slideIndexes: number[], scrollProgress: ScrollProgressType): ScrollSnapListType;
export {};
