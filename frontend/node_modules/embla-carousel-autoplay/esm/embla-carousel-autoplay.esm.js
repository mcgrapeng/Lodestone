const defaultOptions = {
  active: true,
  breakpoints: {},
  delay: 4000,
  instant: false,
  defaultInteraction: true,
  stopOnLastSnap: false,
  rootNode: null
};

function normalizeDelay(emblaApi, delay) {
  const scrollSnaps = emblaApi.snapList();
  if (typeof delay === 'number') {
    return scrollSnaps.map(() => delay);
  }
  return delay(scrollSnaps, emblaApi);
}
function getAutoplayRootNode(emblaApi, rootNode) {
  const emblaRootNode = emblaApi.rootNode();
  return rootNode && rootNode(emblaRootNode) || emblaRootNode;
}

function Autoplay(userOptions = {}) {
  let options;
  let emblaApi;
  let isSsr = false;
  let destroyed = false;
  let delay;
  let pauseDelay = null;
  let timerStartTime = null;
  let timerId = 0;
  let autoplayRunning = false;
  let playOnDocumentVisible = false;
  let instant = false;
  let isMouseOver = false;
  let isPointerDown = false;
  let onInteraction = onDefaultInteraction;
  function pluginIsActive() {
    if (isSsr) return false;
    if (destroyed) return false;
    return options.active;
  }
  function init(emblaApiInstance, optionsHandler) {
    emblaApi = emblaApiInstance;
    const {
      mergeOptions,
      optionsAtMedia
    } = optionsHandler;
    const optionsBase = mergeOptions(defaultOptions, Autoplay.globalOptions);
    const allOptions = mergeOptions(optionsBase, userOptions);
    destroyed = false;
    options = optionsAtMedia(allOptions);
    isSsr = emblaApi.internalEngine().isSsr;
    if (!pluginIsActive()) return;
    if (emblaApi.snapList().length <= 1) return;
    instant = options.instant;
    delay = normalizeDelay(emblaApi, options.delay);
    onInteraction = options.defaultInteraction ? onDefaultInteraction : onCustomInteraction;
    const {
      eventStore,
      nodeHandler
    } = emblaApi.internalEngine();
    const {
      ownerDocument
    } = nodeHandler;
    const root = getAutoplayRootNode(emblaApi, options.rootNode);
    if (ownerDocument) {
      eventStore.add(ownerDocument, 'visibilitychange', onVisibilityChange);
    }
    emblaApi.on('pointerdown', onInteraction);
    emblaApi.on('pointerup', onInteraction);
    emblaApi.on('slidefocus', onInteraction);
    eventStore.add(root, 'mouseenter', event => onInteraction(emblaApi, event, event.type));
    eventStore.add(root, 'mouseleave', event => onInteraction(emblaApi, event, event.type));
    eventStore.add(emblaApi.containerNode(), 'focusout', event => onInteraction(emblaApi, event, 'slidefocusout'));
  }
  function destroy() {
    if (!pluginIsActive()) return;
    emblaApi.off('pointerdown', onInteraction).off('pointerup', onInteraction).off('slidefocus', onInteraction);
    stopAutoplay();
    destroyed = true;
    autoplayRunning = false;
  }
  function setTimer() {
    const {
      ownerWindow
    } = emblaApi.internalEngine().nodeHandler;
    if (!ownerWindow) return;
    const startTime = new Date().getTime();
    const event = emblaApi.createEvent('autoplay:timerset', {
      startTime
    });
    ownerWindow.clearTimeout(timerId);
    timerId = ownerWindow.setTimeout(next, getDelay());
    timerStartTime = startTime;
    event.emit();
  }
  function clearTimer() {
    const {
      ownerWindow
    } = emblaApi.internalEngine().nodeHandler;
    if (!ownerWindow) return;
    const stopTime = new Date().getTime();
    const event = emblaApi.createEvent('autoplay:timerstopped', {
      stopTime
    });
    ownerWindow.clearTimeout(timerId);
    timerId = 0;
    timerStartTime = null;
    event.emit();
  }
  function startAutoplay() {
    if (!pluginIsActive()) return;
    if (documentIsHidden()) {
      playOnDocumentVisible = true;
      return;
    }
    if (!autoplayRunning) {
      autoplayRunning = true;
      const event = emblaApi.createEvent('autoplay:play', null);
      event.emit();
    }
    setTimer();
  }
  function stopAutoplay() {
    if (!pluginIsActive()) return;
    if (autoplayRunning) {
      autoplayRunning = false;
      const event = emblaApi.createEvent('autoplay:stop', null);
      event.emit();
    }
    clearTimer();
  }
  function onVisibilityChange() {
    if (documentIsHidden()) {
      playOnDocumentVisible = autoplayRunning;
      return stopAutoplay();
    }
    if (playOnDocumentVisible) startAutoplay();
  }
  function documentIsHidden() {
    const {
      ownerDocument
    } = emblaApi.internalEngine().nodeHandler;
    if (!ownerDocument) return false;
    return ownerDocument.visibilityState === 'hidden';
  }
  function onDefaultInteraction(_, originalEvent, customType) {
    const type = originalEvent.type;
    const interaction = customType || type;
    if (interaction === 'slidefocus') stopAutoplay();
    if (interaction === 'pointerdown') stopAutoplay();
  }
  function onCustomInteraction(_, originalEvent, customType) {
    const type = originalEvent.type;
    const interaction = customType || type;
    if (interaction === 'mouseenter') isMouseOver = true;
    if (interaction === 'mouseleave') isMouseOver = false;
    if (interaction === 'pointerdown') isPointerDown = true;
    if (interaction === 'pointerup') isPointerDown = false;
    const event = emblaApi.createEvent('autoplay:interaction', {
      interaction,
      originalEvent,
      isMouseOver,
      isPointerDown
    });
    event.emit();
  }
  function play(instantOverride) {
    instant = instantOverride !== null && instantOverride !== void 0 ? instantOverride : instant;
    startAutoplay();
  }
  function stop() {
    if (autoplayRunning) stopAutoplay();
  }
  function reset() {
    if (autoplayRunning) startAutoplay();
    pauseDelay = null;
  }
  function pause() {
    if (!autoplayRunning) return;
    pauseDelay = timeUntilNext();
    stopAutoplay();
  }
  function isPlaying() {
    return autoplayRunning;
  }
  function next() {
    const {
      indexCurrent
    } = emblaApi.internalEngine();
    const nextIndex = indexCurrent.clone().add(1).get();
    const lastIndex = emblaApi.snapList().length - 1;
    const kill = options.stopOnLastSnap && nextIndex === lastIndex;
    const event = emblaApi.createEvent('autoplay:select', {
      targetSnap: emblaApi.canGoToNext() ? nextIndex : 0,
      sourceSnap: indexCurrent.get()
    });
    if (emblaApi.canGoToNext()) {
      emblaApi.goToNext(instant);
    } else {
      emblaApi.goTo(0, instant);
    }
    event.emit();
    pauseDelay = null;
    if (kill) return stopAutoplay();
    startAutoplay();
  }
  function getDelay() {
    return pauseDelay || delay[emblaApi.selectedSnap()];
  }
  function timeUntilNext() {
    if (!pluginIsActive()) return null;
    if (!timerStartTime) return null;
    const timePastSinceStart = new Date().getTime() - timerStartTime;
    return getDelay() - timePastSinceStart;
  }
  const self = {
    name: 'autoplay',
    options: userOptions,
    init,
    destroy,
    play,
    stop,
    reset,
    pause,
    isPlaying,
    timeUntilNext
  };
  return self;
}
Autoplay.globalOptions = undefined;

export { Autoplay as default };
//# sourceMappingURL=embla-carousel-autoplay.esm.js.map
