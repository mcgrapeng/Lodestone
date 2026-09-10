import { OptionsHandlerType } from './OptionsHandler.js';
import { CreateOptionsType, OptionsType } from './Options.js';
import { EngineType } from './Engine.js';
import { NodesType } from './NodeHandler.js';
import { CreatePluginType } from './Plugins.js';
export type EmblaSsrHandlerType = {
    getNodes: () => NodesType;
    getStyles: (containerSelector: string, slidesSelector?: string) => string;
    setup(createEngine: (options: OptionsType, container: HTMLElement, slides: HTMLElement[], useCachedRects?: boolean) => EngineType, mergeOptions: OptionsHandlerType['mergeOptions'], options: OptionsType): void;
};
export type EmblaSsrOptionsType = Omit<CreateOptionsType<{
    slideSizes: number[];
}>, 'active'>;
export type EmblaSsrType = CreatePluginType<EmblaSsrHandlerType, EmblaSsrOptionsType>;
