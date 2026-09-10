const defaultOptions = {
  active: true,
  breakpoints: {},
  announceChanges: false,
  carouselAriaLabel: 'Carousel',
  carouselAriaRoleDescription: 'carousel',
  carouselRole: 'region',
  previousButtonAriaLabel: 'Go to previous Slide',
  nextButtonAriaLabel: 'Go to next Slide',
  slideAriaRoleDescription: 'slide',
  slideRole: 'group',
  rootNode: null,
  slideAriaLabel: (hasAnyGroupedSlides, firstSlideIndex, lastSlideIndex, totalSlides, selectedSnapIndex, totalSnaps) => {
    const slide = firstSlideIndex + 1;
    const lastSlide = lastSlideIndex + 1;
    const isGrouped = firstSlideIndex !== lastSlideIndex;
    const groupInfo = `(group ${selectedSnapIndex + 1} of ${totalSnaps})`;
    if (!hasAnyGroupedSlides) {
      return `Slide ${slide} of ${totalSlides}`;
    }
    if (!isGrouped) {
      return `Slide ${slide} of ${totalSlides} ${groupInfo}`;
    }
    return `Slides ${slide}-${lastSlide} of ${totalSlides} ${groupInfo}`;
  },
  dotButtonAriaLabel: (hasAnyGroupedSlides, firstSlideIndex, lastSlideIndex, totalSlides, selectedSnapIndex, totalSnaps) => {
    const slide = firstSlideIndex + 1;
    const lastSlide = lastSlideIndex + 1;
    const isSlideGrouped = firstSlideIndex !== lastSlideIndex;
    const groupInfo = `(group ${selectedSnapIndex + 1} of ${totalSnaps})`;
    if (!hasAnyGroupedSlides) {
      return `Go to slide ${slide} of ${totalSlides}`;
    }
    if (!isSlideGrouped) {
      return `Go to slide ${slide} of ${totalSlides} ${groupInfo}`;
    }
    return `Go to slides ${slide}-${lastSlide} of ${totalSlides} ${groupInfo}`;
  },
  liveRegionContent: (hasAnyGroupedSlides, firstSlideIndex, lastSlideIndex, totalSlides, selectedSnapIndex, totalSnaps) => {
    const slide = firstSlideIndex + 1;
    const lastSlide = lastSlideIndex + 1;
    const isSlideGrouped = firstSlideIndex !== lastSlideIndex;
    const groupInfo = `(group ${selectedSnapIndex + 1} of ${totalSnaps})`;
    if (!hasAnyGroupedSlides) {
      return `Showing slide ${slide} of ${totalSlides}`;
    }
    if (!isSlideGrouped) {
      return `Showing slide ${slide} of ${totalSlides} ${groupInfo}`;
    }
    return `Showing slides ${slide}-${lastSlide} of ${totalSlides} ${groupInfo}`;
  }
};

function AttributeHandler(initialNode) {
  const attributeStore = new Map();
  let node = initialNode || null;
  function connect(element) {
    node = element;
  }
  function set(key, value) {
    if (!node) return;
    if (!value) return;
    attributeStore.set(key, value);
    node.setAttribute(key, value);
  }
  function toggle(key, value) {
    if (!node) return;
    if (!value) return remove(key);
    set(key, value.toString());
  }
  function remove(key) {
    if (!node) return;
    attributeStore.delete(key);
    node.removeAttribute(key);
  }
  function removeAll() {
    if (!node) return;
    attributeStore.forEach((_, key) => remove(key));
    attributeStore.clear();
  }
  const self = {
    connect,
    set,
    toggle,
    remove,
    removeAll
  };
  return self;
}

function isString(value) {
  return typeof value === 'string';
}
function getChildNode(root, subject) {
  const node = isString(subject) ? root.querySelector(subject) : subject;
  return node;
}
function getChildNodes(root, subject) {
  const node = isString(subject) ? root.querySelectorAll(subject) : subject;
  return node ? Array.from(node) : [];
}
function getAccessibilityRootNode(emblaApi, rootNode) {
  const emblaRootNode = emblaApi.rootNode();
  return rootNode && rootNode(emblaRootNode) || emblaRootNode;
}

function Accessibility(userOptions = {}) {
  const focusableSelectors = ['a[href]', 'area[href]', 'input:not([type="hidden"]):not([disabled])', 'select:not([disabled])', 'textarea:not([disabled])', 'button:not([disabled])', 'iframe', 'summary', 'details', 'object', 'embed', 'audio[controls]', 'video[controls]', '[tabindex]:not([tabindex="-1"])', '[contenteditable]:not([contenteditable="false"])'];
  const focusSelector = focusableSelectors.map(selector => `${selector}:not([hidden])`).join(',');
  let options;
  let emblaApi;
  let isSsr = false;
  let destroyed = false;
  let rootNode;
  let liveRegionNode = null;
  let dotsObserver = null;
  let allSnaps = [];
  let isUpdatingLiveRegion = false;
  let lastFocusedSlide = null;
  let focusNodesBySlide = [];
  let rootAttributes;
  let prevButtonAttributes;
  let nextButtonAttributes;
  let liveRegionAttributes;
  let dotsAttributes = [];
  let slidesAttributes = [];
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
    const optionsBase = mergeOptions(defaultOptions, Accessibility.globalOptions);
    const allOptions = mergeOptions(optionsBase, userOptions);
    destroyed = false;
    options = optionsAtMedia(allOptions);
    isSsr = emblaApi.internalEngine().isSsr;
    if (!pluginIsActive()) return;
    rootAttributes = AttributeHandler();
    prevButtonAttributes = AttributeHandler();
    nextButtonAttributes = AttributeHandler();
    liveRegionAttributes = AttributeHandler();
    dotsAttributes = emblaApi.snapList().map(() => AttributeHandler());
    slidesAttributes = emblaApi.slideNodes().map(() => AttributeHandler());
    rootNode = getAccessibilityRootNode(emblaApi, options.rootNode);
    allSnaps = emblaApi.snapList().map((_, index) => index);
    focusNodesBySlide = emblaApi.slideNodes().map(() => []);
    isUpdatingLiveRegion = options.announceChanges;
    setupCarousel();
    setupSlides();
    emblaApi.on('select', onSelect);
  }
  function destroy() {
    if (!pluginIsActive()) return;
    emblaApi.off('select', onSelect);
    rootAttributes.removeAll();
    prevButtonAttributes.removeAll();
    nextButtonAttributes.removeAll();
    liveRegionAttributes.removeAll();
    slidesAttributes.forEach(slideAttributes => slideAttributes.removeAll());
    dotsAttributes.forEach(dotAttributes => dotAttributes.removeAll());
    focusNodesBySlide.flat().forEach(slideFocusNode => {
      const {
        focusAttributes,
        prevTabIndex
      } = slideFocusNode;
      focusAttributes.toggle('tabindex', prevTabIndex);
    });
  }
  function setupCarousel() {
    if (!pluginIsActive()) return;
    const {
      carouselRole,
      carouselAriaLabel,
      carouselAriaRoleDescription
    } = options;
    if (dotsObserver) dotsObserver.disconnect();
    rootAttributes.connect(emblaApi.rootNode());
    rootAttributes.set('role', carouselRole);
    rootAttributes.set('aria-label', carouselAriaLabel);
    rootAttributes.set('aria-roledescription', carouselAriaRoleDescription);
  }
  function onSlideFocusIn(slideIndex) {
    return () => {
      lastFocusedSlide = slideIndex;
      const {
        snapBySlide
      } = emblaApi.internalEngine().scrollSnapList;
      const snapIndex = snapBySlide[lastFocusedSlide];
      updateSlides([snapIndex]);
    };
  }
  function onSlideFocusOut() {
    if (lastFocusedSlide === null || lastFocusedSlide < 0) return;
    const {
      snapBySlide
    } = emblaApi.internalEngine().scrollSnapList;
    const snapIndex = snapBySlide[lastFocusedSlide];
    updateSlides([snapIndex]);
    lastFocusedSlide = null;
  }
  function setupSlides() {
    if (!pluginIsActive()) return;
    const {
      scrollSnapList,
      eventStore
    } = emblaApi.internalEngine();
    const {
      slideRole,
      slideAriaRoleDescription,
      slideAriaLabel
    } = options;
    const focusOptions = {
      capture: true
    };
    emblaApi.slideNodes().forEach((slideNode, slideIndex) => {
      const snapIndex = scrollSnapList.snapBySlide[slideIndex];
      const label = getAriaText(snapIndex, slideAriaLabel);
      const slideAttributes = slidesAttributes[slideIndex];
      const slideFocusNodes = getChildNodes(slideNode, focusSelector);
      slideAttributes.connect(slideNode);
      slideAttributes.set('role', slideRole);
      slideAttributes.set('aria-roledescription', slideAriaRoleDescription);
      slideAttributes.set('aria-label', label);
      eventStore.add(slideNode, 'focusout', onSlideFocusOut, focusOptions);
      eventStore.add(slideNode, 'focusin', onSlideFocusIn(slideIndex), focusOptions);
      focusNodesBySlide[slideIndex] = slideFocusNodes.map(focusNode => ({
        focusAttributes: AttributeHandler(focusNode),
        prevTabIndex: focusNode.getAttribute('tabindex')
      }));
    });
    updateSlides();
  }
  function setupDotButtons(dotsWrapper) {
    if (!pluginIsActive()) return;
    const {
      dotButtonAriaLabel
    } = options;
    const wrapper = getChildNode(rootNode, dotsWrapper);
    const dotNodes = getChildNodes(wrapper, wrapper === null || wrapper === void 0 ? void 0 : wrapper.children);
    dotsAttributes = dotNodes.map(() => AttributeHandler());
    dotNodes.forEach((dotNode, snapIndex) => {
      const label = getAriaText(snapIndex, dotButtonAriaLabel);
      const dotAttributes = dotsAttributes[snapIndex];
      dotAttributes.connect(dotNode);
      dotAttributes.set('aria-label', label);
    });
    if (wrapper) {
      if (dotsObserver) dotsObserver.disconnect();
      dotsObserver = new MutationObserver(() => setupDotButtons(dotsWrapper));
      dotsObserver.observe(wrapper, {
        childList: true
      });
    }
    updateDotButtons();
  }
  function setupPrevAndNextButtons(prevButton, nextButton) {
    if (!pluginIsActive()) return;
    const {
      previousButtonAriaLabel,
      nextButtonAriaLabel
    } = options;
    prevButtonAttributes.connect(getChildNode(rootNode, prevButton));
    prevButtonAttributes.set('aria-label', previousButtonAriaLabel);
    nextButtonAttributes.connect(getChildNode(rootNode, nextButton));
    nextButtonAttributes.set('aria-label', nextButtonAriaLabel);
    updatePrevAndNextButtons();
  }
  function setupLiveRegion(liveRegion) {
    if (!pluginIsActive()) return;
    liveRegionNode = getChildNode(rootNode, liveRegion);
    liveRegionAttributes.connect(liveRegionNode);
    liveRegionAttributes.set('aria-live', 'polite');
    liveRegionAttributes.set('aria-atomic', 'true');
    updateLiveRegion();
  }
  function onSelect(emblaApi) {
    const previousSnap = emblaApi.previousSnap();
    const selectedSnap = emblaApi.selectedSnap();
    const snapsToUpdate = [selectedSnap];
    if (selectedSnap !== previousSnap) snapsToUpdate.push(previousSnap);
    updateSlides(snapsToUpdate);
    updateDotButtons(snapsToUpdate);
    updatePrevAndNextButtons();
    updateLiveRegion();
  }
  function setUpdateLiveRegion(enable) {
    isUpdatingLiveRegion = enable;
    updateLiveRegion();
  }
  function updateLiveRegion() {
    if (!pluginIsActive()) return;
    if (!liveRegionNode) return;
    if (!isUpdatingLiveRegion) return;
    if (!options.liveRegionContent) return;
    const snapIndex = emblaApi.selectedSnap();
    const label = getAriaText(snapIndex, options.liveRegionContent);
    if (label) liveRegionNode.innerHTML = label;
  }
  function updatePrevAndNextButtons() {
    const isPrevDisabled = !emblaApi.canGoToPrev();
    const isNextDisabled = !emblaApi.canGoToNext();
    prevButtonAttributes.toggle('aria-disabled', isPrevDisabled);
    nextButtonAttributes.toggle('aria-disabled', isNextDisabled);
  }
  function updateDotButtons(snaps = allSnaps) {
    snaps.forEach(snapIndex => {
      const isActive = snapIndex === emblaApi.selectedSnap();
      const dotAttributes = dotsAttributes[snapIndex];
      if (!dotAttributes) return;
      dotAttributes.toggle('aria-current', isActive);
    });
  }
  function updateSlides(snaps = allSnaps) {
    const {
      slidesBySnap
    } = emblaApi.internalEngine().scrollSnapList;
    snaps.forEach(snapIndex => {
      const slidesInSnap = slidesBySnap[snapIndex];
      const isActive = snapIndex === emblaApi.selectedSnap();
      slidesInSnap.forEach(slideIndex => {
        const slideNode = emblaApi.slideNodes()[slideIndex];
        const hasFocusedElement = slideNode.contains(document.activeElement);
        const slideAttributes = slidesAttributes[slideIndex];
        const slideFocusNodes = focusNodesBySlide[slideIndex];
        slideAttributes.toggle('aria-hidden', !isActive && !hasFocusedElement);
        slideFocusNodes.forEach(slideFocusNode => {
          const {
            focusAttributes,
            prevTabIndex
          } = slideFocusNode;
          const tabindex = !isActive ? '-1' : prevTabIndex;
          focusAttributes.toggle('tabindex', tabindex);
        });
      });
    });
  }
  function getAriaText(snapIndex, ariaTextCallback) {
    const {
      slidesBySnap
    } = emblaApi.internalEngine().scrollSnapList;
    const slidesInSnap = slidesBySnap[snapIndex];
    if (!ariaTextCallback) return '';
    if (!allSnaps.length) return '';
    if (!slidesInSnap) return '';
    const hasSlideGroups = slidesBySnap.some(group => group.length > 1);
    const slideCount = emblaApi.slideNodes().length;
    const snapCount = allSnaps.length;
    return ariaTextCallback(hasSlideGroups, slidesInSnap[0], slidesInSnap[slidesInSnap.length - 1], slideCount, snapIndex, snapCount);
  }
  const self = {
    name: 'accessibility',
    options: userOptions,
    init,
    destroy,
    setupPrevAndNextButtons,
    setupDotButtons,
    setupLiveRegion,
    setUpdateLiveRegion,
    updateSlides,
    updateDotButtons,
    updatePrevAndNextButtons,
    updateLiveRegion
  };
  return self;
}
Accessibility.globalOptions = undefined;

export { Accessibility as default };
//# sourceMappingURL=embla-carousel-accessibility.esm.js.map
