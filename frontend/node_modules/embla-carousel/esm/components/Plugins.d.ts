import { CreateOptionsType, LooseOptionsType } from './Options.js';
import { EmblaCarouselType } from './EmblaCarousel.js';
import { OptionsHandlerType } from './OptionsHandler.js';
export type LoosePluginType = {
    [key: string]: unknown;
};
export type CreatePluginType<TypeA extends LoosePluginType, TypeB extends LooseOptionsType> = TypeA & {
    name: string;
    options: Partial<CreateOptionsType<TypeB>>;
    init: (emblaApi: EmblaCarouselType, OptionsHandler: OptionsHandlerType) => void;
    destroy: () => void;
};
export interface EmblaPluginsType {
    [key: string]: CreatePluginType<LoosePluginType, {}> | undefined;
}
export type EmblaPluginType = NonNullable<EmblaPluginsType[keyof EmblaPluginsType]>;
