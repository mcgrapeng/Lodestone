import { EngineType } from './Engine.js';
import { EventHandlerType } from './EventHandler.js';
import { EmblaOptionsType } from './Options.js';
import { EmblaPluginsType, EmblaPluginType } from './Plugins.js';
import { ScrollToDirectionType } from './ScrollTo.js';
export type EmblaCarouselType = {
    canGoToNext: () => boolean;
    canGoToPrev: () => boolean;
    goToNext: (instant?: boolean) => void;
    goToPrev: (instant?: boolean) => void;
    goTo: (index: number, instant?: boolean, direction?: ScrollToDirectionType) => void;
    previousSnap: () => number;
    selectedSnap: () => number;
    rootNode: () => HTMLElement;
    containerNode: () => HTMLElement;
    slideNodes: () => HTMLElement[];
    snapIndex: (offset: number) => number;
    snapList: () => number[];
    createEvent: EventHandlerType['createEvent'];
    destroy: () => void;
    on: EventHandlerType['on'];
    off: EventHandlerType['off'];
    internalEngine: () => EngineType;
    cloneEngine: (userOptions?: EmblaOptionsType) => EngineType;
    plugins: () => EmblaPluginsType;
    reInit: (options?: EmblaOptionsType, plugins?: EmblaPluginType[]) => void;
    scrollProgress: () => number;
    slidesInView: () => number[];
};
declare function EmblaCarousel(userRoot?: HTMLElement | null, userOptions?: EmblaOptionsType | null, userPlugins?: EmblaPluginType[] | null): EmblaCarouselType;
declare namespace EmblaCarousel {
    let globalOptions: EmblaOptionsType | undefined;
}
export default EmblaCarousel;
