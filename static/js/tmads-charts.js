/**
 * TMADS — Executive chart presets (ECharts 5)
 */
(function (global) {
  const COLORS = {
    impressions: "#2AABEE",
    clicks: "#177DC7",
    actions: "#16866A",
    spent: "#7D8FA5",
    ctr: "#B7791F",
    grid: "#E3EAF1",
    muted: "#718198",
    heading: "#243449",
  };

  const FA_FONT = "Vazirmatn, Tahoma, sans-serif";

  function baseGrid(extra) {
    return Object.assign(
      { left: 52, right: 28, top: 36, bottom: 48, containLabel: true },
      extra || {}
    );
  }

  function formatCountAxis(v) {
    const n = Number(v);
    if (Number.isNaN(n)) return "";
    const abs = Math.abs(n);
    if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(".", "٫") + "M";
    if (abs >= 10_000) return Math.round(n / 1_000) + "K";
    if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(".", "٫") + "K";
    return String(Math.round(n));
  }

  function formatPct(v) {
    const n = Number(v);
    if (Number.isNaN(n)) return "—";
    return (Math.round(n * 10) / 10).toString().replace(".", "٫") + "٪";
  }

  function formatCountFull(v) {
    const n = Number(v);
    if (Number.isNaN(n)) return "—";
    try {
      return n.toLocaleString("fa-IR");
    } catch (_e) {
      return formatCountAxis(v);
    }
  }

  function barFill(top, bottom) {
    return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: top },
      { offset: 1, color: bottom },
    ]);
  }

  function areaFill(rgb) {
    return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: `rgba(${rgb}, 0.28)` },
      { offset: 1, color: `rgba(${rgb}, 0.02)` },
    ]);
  }

  function axisSideCount(name, color, position) {
    const isLeft = (position || "left") === "left";
    return {
      type: "value",
      name: name || "",
      position: position || "right",
      nameTextStyle: { color: color || COLORS.muted, fontFamily: FA_FONT, fontSize: 10 },
      alignTicks: false,
      splitLine: {
        show: isLeft,
        lineStyle: { type: "dashed", color: COLORS.grid },
      },
      axisLine: { show: false },
      axisLabel: {
        color: color || COLORS.muted,
        fontFamily: FA_FONT,
        formatter: formatCountAxis,
        margin: 10,
      },
    };
  }

  function axisCategory(labels, opts) {
    const many = labels.length > 12;
    return {
      type: "category",
      data: labels,
      boundaryGap: true,
      axisLine: { lineStyle: { color: COLORS.grid } },
      axisLabel: {
        color: COLORS.muted,
        fontFamily: FA_FONT,
        fontSize: 11,
        hideOverlap: true,
        rotate: many ? 32 : 0,
        interval: many ? Math.max(0, Math.floor(labels.length / 10)) : 0,
      },
      axisTick: { show: false },
    };
  }

  function axisCount(name) {
    return {
      type: "value",
      name: name || "",
      nameTextStyle: { color: COLORS.muted, fontFamily: FA_FONT, fontSize: 11 },
      splitLine: { lineStyle: { type: "dashed", color: COLORS.grid } },
      axisLabel: {
        color: COLORS.muted,
        fontFamily: FA_FONT,
        formatter: formatCountAxis,
        margin: 8,
      },
    };
  }

  function axisCtr() {
    return {
      type: "value",
      min: 0,
      position: "right",
      alignTicks: false,
      splitLine: { show: false },
      axisLabel: {
        color: COLORS.ctr,
        fontFamily: FA_FONT,
        formatter: formatPct,
        margin: 8,
      },
    };
  }

  function tooltipAxis(extra) {
    return Object.assign(
      {
        trigger: "axis",
        padding: [10, 14],
        backgroundColor: "rgba(255,255,255,0.97)",
        borderColor: COLORS.grid,
        borderWidth: 1,
        extraCssText: "box-shadow: 0 12px 32px rgba(16,31,51,0.12); border-radius: 12px;",
        textStyle: { color: COLORS.heading, fontFamily: FA_FONT, fontSize: 12 },
        axisPointer: {
          type: "shadow",
          shadowStyle: { color: "rgba(42, 171, 238, 0.08)" },
          lineStyle: { color: "rgba(23, 125, 199, 0.35)", type: "dashed", width: 1 },
        },
        confine: true,
      },
      extra || {}
    );
  }

  function tooltipHeader(label) {
    return `<div style="font-weight:600;margin-bottom:6px;color:${COLORS.heading}">${label}</div>`;
  }

  function init(el) {
    if (!el || typeof echarts === "undefined") return null;
    const existing = echarts.getInstanceByDom(el);
    if (existing) {
      existing.dispose();
    }
    return echarts.init(el, null, { renderer: "canvas", locale: "FA" });
  }

  function sliceHasSignal(data) {
    if (!data || !Array.isArray(data.dates) || !data.dates.length) {
      return false;
    }
    const keys = ["impressions", "clicks", "actions", "spent"];
    for (const key of keys) {
      const series = data[key] || [];
      for (const v of series) {
        const n = key === "spent" ? Number(v) : Number.parseInt(v, 10);
        if (!Number.isNaN(n) && n > 0) {
          return true;
        }
      }
    }
    return false;
  }

  /** اگر بازهٔ انتخابی فقط صفر باشد (مثلاً کمپین متوقف)، کل دوره را پیشنهاد می‌دهد. */
  function suggestChartRangeDays(data, preferred) {
    if (!data || !Array.isArray(data.dates) || !data.dates.length) {
      return preferred || 30;
    }
    const total = data.dates.length;
    if (total < 7) {
      return 0;
    }
    const pref = preferred && preferred > 0 ? preferred : 30;
    if (pref > 0 && pref < total) {
      const tail = slicePeriodData(data, pref);
      if (sliceHasSignal(tail)) {
        return pref;
      }
    }
    return 0;
  }

  function slicePeriodData(data, days) {
    if (!data || !Array.isArray(data.dates) || !data.dates.length) {
      return data;
    }
    const total = data.dates.length;
    if (!days || days <= 0 || days >= total) {
      return data;
    }
    const start = total - days;
    const tail = (arr) => (Array.isArray(arr) ? arr.slice(start) : arr);
    const lbl = data.date_labels && data.date_labels.length ? data.date_labels : data.dates;
    return {
      dates: data.dates.slice(start),
      date_labels: tail(lbl),
      impressions: tail(data.impressions),
      clicks: tail(data.clicks),
      actions: tail(data.actions),
      spent: tail(data.spent),
      ctr: tail(data.ctr),
      day_count: days,
      from_date: data.dates[start],
      to_date: data.dates[total - 1],
    };
  }

  function labels(data) {
    return (data.date_labels && data.date_labels.length) ? data.date_labels : data.dates;
  }

  function performanceChart(el, data, options) {
    const chart = init(el);
    if (!chart || !data.dates || !data.dates.length) return null;
    const opts = options || {};
    const lbl = labels(data);
    const portfolio = Boolean(opts.portfolio);
    const analyticsMode = Boolean(opts.analyticsMode);
    const overviewMini = Boolean(opts.overviewMini);
    const compact = Boolean(opts.compact);
    const useArea = !compact;
    const showCtr = Boolean(opts.showCtr) && !portfolio;
    const legendItems = portfolio ? ["نمایش", "کلیک"] : ["نمایش", "کلیک", "ورود"];
    if (showCtr) legendItems.push("نرخ کلیک");

    const impressionsSeries = {
      name: "نمایش",
      type: useArea ? "line" : "bar",
      smooth: true,
      data: data.impressions,
      showSymbol: !portfolio && lbl.length <= 16,
      symbolSize: 7,
      yAxisIndex: 0,
      z: 1,
      emphasis: { focus: "series" },
    };

    if (useArea) {
      impressionsSeries.lineStyle = { width: 2.75, color: COLORS.impressions };
      impressionsSeries.itemStyle = { color: COLORS.impressions, borderWidth: 2, borderColor: "#fff" };
      impressionsSeries.areaStyle = { color: areaFill("42, 171, 238") };
    } else {
      impressionsSeries.barMaxWidth = portfolio ? 20 : 24;
      impressionsSeries.barGap = portfolio ? "35%" : "22%";
      impressionsSeries.itemStyle = {
        borderRadius: [6, 6, 2, 2],
        color: barFill("#6CC8F6", "#2AABEE"),
        shadowColor: "rgba(42, 171, 238, 0.25)",
        shadowBlur: 6,
        shadowOffsetY: 2,
      };
      impressionsSeries.emphasis = {
        itemStyle: {
          color: barFill("#8ED4F9", "#177DC7"),
          shadowBlur: 12,
        },
      };
    }

    const clicksSeries = {
      name: "کلیک",
      type: "line",
      smooth: 0.35,
      data: data.clicks,
      showSymbol: true,
      symbol: "circle",
      symbolSize: portfolio ? 7 : 6,
      lineStyle: {
        width: portfolio ? 2.5 : 2.5,
        color: COLORS.clicks,
        shadowColor: "rgba(23, 125, 199, 0.35)",
        shadowBlur: 4,
        shadowOffsetY: 2,
      },
      itemStyle: {
        color: "#fff",
        borderColor: COLORS.clicks,
        borderWidth: 2,
      },
      yAxisIndex: portfolio ? 1 : 0,
      z: 3,
      emphasis: { focus: "series", scale: true },
    };

    if (portfolio) {
      clicksSeries.areaStyle = { color: areaFill("23, 125, 199") };
    }

    const series = [impressionsSeries, clicksSeries];

    if (!portfolio) {
      series.push({
        name: "ورود",
        type: "line",
        smooth: true,
        data: data.actions,
        showSymbol: lbl.length <= 20,
        symbolSize: 6,
        lineStyle: { width: 2, color: COLORS.actions },
        itemStyle: { color: COLORS.actions },
        yAxisIndex: 0,
        z: 2,
      });
    }

    if (showCtr && data.ctr && data.ctr.length) {
      series.push({
        name: "نرخ کلیک",
        type: "line",
        smooth: true,
        data: data.ctr,
        showSymbol: false,
        lineStyle: { width: 1.5, type: "dashed", color: COLORS.ctr },
        itemStyle: { color: COLORS.ctr },
        yAxisIndex: 1,
        z: 4,
      });
    }

    let yAxis;
    if (portfolio) {
      const hideAxisNames = overviewMini || (compact && !opts.showAxisNames);
      yAxis = [
        axisSideCount(hideAxisNames ? "" : "نمایش", COLORS.impressions, "left"),
        axisSideCount(hideAxisNames ? "" : "کلیک", COLORS.clicks, "right"),
      ];
    } else {
      yAxis = [axisCount("تعداد")];
      if (showCtr && data.ctr && data.ctr.length) {
        yAxis.push(axisCtr());
      }
    }

    const gridDefaults = {
      containLabel: true,
      left: overviewMini ? 2 : 10,
      right: overviewMini ? 2 : portfolio ? 10 : showCtr ? 10 : 8,
    };
    if (overviewMini) {
      gridDefaults.top = 26;
      gridDefaults.bottom = 30;
    } else if (analyticsMode) {
      gridDefaults.top = 40;
    }
    const grid = baseGrid(Object.assign(gridDefaults, opts.grid || {}));

    chart.setOption({
      color: [COLORS.impressions, COLORS.clicks, COLORS.actions, COLORS.ctr],
      grid,
      animationDuration: 720,
      animationEasing: "cubicOut",
      tooltip: tooltipAxis({
        formatter(params) {
          if (!params || !params.length) return "";
          const head = params[0].axisValueLabel || params[0].name;
          let html = tooltipHeader(head);
          params.forEach((p) => {
            const val =
              p.seriesName === "نرخ کلیک"
                ? formatPct(p.data)
                : formatCountFull(p.data);
            html += `<div style="display:flex;align-items:center;gap:8px;margin:3px 0;color:${COLORS.heading}">`;
            html += `<span>${p.marker}</span><span>${p.seriesName}</span>`;
            html += `<strong style="margin-inline-start:auto;font-variant-numeric:tabular-nums">${val}</strong></div>`;
          });
          return html;
        },
      }),
      legend: {
        type: overviewMini || analyticsMode ? "plain" : "scroll",
        data: legendItems,
        top: analyticsMode ? 0 : overviewMini ? 0 : undefined,
        bottom: analyticsMode || overviewMini ? undefined : 2,
        left: analyticsMode || overviewMini ? "center" : undefined,
        itemGap: overviewMini ? 12 : analyticsMode ? 14 : 18,
        itemWidth: 18,
        itemHeight: 10,
        textStyle: { color: COLORS.muted, fontFamily: FA_FONT, fontSize: overviewMini ? 10 : 11 },
        icon: "roundRect",
      },
      xAxis: axisCategory(lbl, opts),
      yAxis,
      series,
      dataZoom: (() => {
        const n = data.dates.length;
        if (analyticsMode && n > 28) {
          const tailPct = Math.min(100, Math.max(18, (28 / n) * 100));
          const start = 100 - tailPct;
          return [
            { type: "inside", start, end: 100, zoomOnMouseWheel: true, moveOnMouseMove: true },
            {
              type: "slider",
              height: 16,
              bottom: 4,
              start,
              end: 100,
              borderColor: "transparent",
              backgroundColor: "rgba(227, 234, 241, 0.65)",
              fillerColor: "rgba(42, 171, 238, 0.12)",
              handleStyle: { color: COLORS.impressions, borderColor: COLORS.impressions },
              dataBackground: { lineStyle: { opacity: 0.25 }, areaStyle: { opacity: 0.08 } },
              textStyle: { color: COLORS.muted, fontFamily: FA_FONT, fontSize: 10 },
            },
          ];
        }
        if (n > 16 && !portfolio) {
          return [{ type: "inside", start: Math.max(0, 100 - (14 / n) * 100), end: 100 }];
        }
        if (portfolio && n > 12) {
          return [{ type: "inside", start: Math.max(0, 100 - (12 / n) * 100), end: 100 }];
        }
        return undefined;
      })(),
    });
    requestAnimationFrame(() => chart.resize());
    global.addEventListener("resize", () => chart.resize());
    return chart;
  }

  function spendChart(el, data, options) {
    const chart = init(el);
    if (!chart || !data.dates || !data.dates.length) return null;
    const opts = options || {};
    const compact = Boolean(opts.compact);
    const premium = Boolean(opts.premium);
    const many = data.dates.length > 20;
    const spentSeries = (data.spent || []).map((v) => Number(v) || 0);
    const peakSpent = Math.max(...spentSeries, 0.0001);
    chart.setOption({
      color: [COLORS.spent],
      grid: baseGrid({
        bottom: compact ? (premium ? 26 : 28) : 40,
        left: premium ? 4 : compact ? 6 : 10,
        right: premium ? 4 : compact ? 6 : 10,
        top: premium ? 4 : compact ? 12 : 36,
      }),
      animationDuration: 650,
      animationEasing: "cubicOut",
      tooltip: tooltipAxis({
        formatter(params) {
          if (!params || !params.length) return "";
          const p = params[0];
          return (
            tooltipHeader(p.axisValueLabel || p.name) +
            `<div style="color:${COLORS.heading}"><strong>${formatCountFull(p.data)}</strong> گرام</div>`
          );
        },
      }),
      xAxis: axisCategory(labels(data), { many }),
      yAxis: {
        ...axisCount(""),
        min: 0,
        max: peakSpent * (premium ? 1.08 : 1.15),
        splitLine: { show: true, lineStyle: { type: "dashed", color: COLORS.grid, opacity: premium ? 0.85 : 1 } },
        axisLabel: { show: !premium || !compact, color: COLORS.muted, fontFamily: FA_FONT, formatter: formatCountAxis },
      },
      series: [
        {
          name: "مصرف روزانه",
          type: "bar",
          data: data.spent || [],
          barMaxWidth: compact ? (premium ? 12 : 14) : 22,
          itemStyle: {
            borderRadius: premium ? [5, 5, 0, 0] : [4, 4, 1, 1],
            color: premium ? barFill("#B8C5CF", "#94A5B3") : barFill("#A8B8C6", "#8A9DAB"),
          },
          emphasis: {
            itemStyle: { color: premium ? barFill("#CDD6DE", "#7A8C9B") : barFill("#BCC9D4", "#6D7F8E") },
          },
        },
      ],
      dataZoom:
        many && compact
          ? [{ type: "inside", start: Math.max(0, 100 - (18 / data.dates.length) * 100), end: 100 }]
          : undefined,
    });
    requestAnimationFrame(() => chart.resize());
    global.addEventListener("resize", () => chart.resize());
    return chart;
  }

  function funnelSegmentGradient(top, bottom) {
    return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: top },
      { offset: 1, color: bottom },
    ]);
  }

  function funnelBandHalf(value, max, minRatio, maxHalf) {
    const ratio = Math.sqrt(Math.max(value, 0) / Math.max(max, 1));
    return maxHalf * Math.max(minRatio, Math.min(1, ratio));
  }

  function renderDomFunnel(el, funnel) {
    const existing = el && global.echarts ? echarts.getInstanceByDom(el) : null;
    if (existing) {
      existing.dispose();
    }
    el.classList.remove("funnel-viz-host--ready");
    const imp = Number(funnel.impressions) || 0;
    const clk = Number(funnel.clicks) || 0;
    const act = Number(funnel.actions) || 0;
    if (!imp && !clk && !act) {
      el.innerHTML = '<p class="muted chart-empty analytics-chart-empty">هنوز داده‌ای برای قیف تبدیل نیست.</p>';
      return null;
    }
    const cx = 140;
    const maxHalf = 124;
    let wTop = maxHalf;
    let wMid = funnelBandHalf(clk, imp, 0.4, maxHalf);
    let wBot = funnelBandHalf(act, imp, 0.28, maxHalf);
    wMid = Math.min(wMid, wTop * 0.9);
    wBot = Math.min(wBot, wMid * 0.86);
    const wTip = Math.max(wBot * 0.76, 18);

    const y0 = 0;
    const y1 = 58;
    const y2 = 114;
    const y3 = 168;

    const pImp = `M ${cx - wTop} ${y0} H ${cx + wTop} L ${cx + wMid} ${y1} H ${cx - wMid} Z`;
    const pClk = `M ${cx - wMid} ${y1} H ${cx + wMid} L ${cx + wBot} ${y2} H ${cx - wBot} Z`;
    const pAct = `M ${cx - wBot} ${y2} H ${cx + wBot} L ${cx + wTip} ${y3} H ${cx - wTip} Z`;

    const txt = (label, value, yLab, yVal) =>
      `<text class="funnel-svg__label" x="${cx}" y="${yLab}" text-anchor="middle">${label}</text>` +
      `<text class="funnel-svg__value" x="${cx}" y="${yVal}" text-anchor="middle">${formatCountFull(value)}</text>`;

    el.innerHTML =
      `<div class="funnel-viz" role="img" aria-label="قیف تبدیل: نمایش ${formatCountFull(imp)}، کلیک ${formatCountFull(clk)}، ورود ${formatCountFull(act)}">` +
      `<svg class="funnel-svg" viewBox="0 0 280 172" xmlns="http://www.w3.org/2000/svg" focusable="false" aria-hidden="true">` +
      `<defs>` +
      `<linearGradient id="tmads-fg-imp" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#5ecdf9"/><stop offset="100%" stop-color="#2aabee"/></linearGradient>` +
      `<linearGradient id="tmads-fg-clk" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#4298cf"/><stop offset="100%" stop-color="#177dc7"/></linearGradient>` +
      `<linearGradient id="tmads-fg-act" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#22a882"/><stop offset="100%" stop-color="#16866a"/></linearGradient>` +
      `<filter id="tmads-fg-shadow" x="-12%" y="-8%" width="124%" height="120%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#243449" flood-opacity="0.12"/></filter>` +
      `</defs>` +
      `<g filter="url(#tmads-fg-shadow)">` +
      `<path d="${pImp}" fill="url(#tmads-fg-imp)"/>` +
      `<path d="${pClk}" fill="url(#tmads-fg-clk)"/>` +
      `<path d="${pAct}" fill="url(#tmads-fg-act)"/>` +
      `</g>` +
      `<g class="funnel-svg__texts">` +
      txt("نمایش", imp, 26, 46) +
      txt("کلیک", clk, 82, 102) +
      txt("ورود", act, 138, 158) +
      `</g>` +
      `</svg></div>`;
    el.classList.add("funnel-viz-host--ready");
    return { el };
  }

  function conversionFunnelChart(el, funnel, options) {
    const opts = options || {};
    const imp = Number(funnel.impressions) || 0;
    const clk = Number(funnel.clicks) || 0;
    const act = Number(funnel.actions) || 0;
    if (!imp && !clk && !act) {
      el.innerHTML = '<p class="muted chart-empty analytics-chart-empty">هنوز داده‌ای برای قیف تبدیل نیست.</p>';
      return null;
    }
    if (opts.premium !== false) {
      return renderDomFunnel(el, funnel);
    }

    const chart = init(el);
    if (!chart) return null;
    const maxVal = Math.max(imp, clk, act, 1);
    const shareOfImpressions = (v) => (imp > 0 ? formatPct((v / imp) * 100) : "—");
    const steps = [
      { name: "نمایش", value: imp, itemStyle: { color: funnelSegmentGradient("#4BC4F7", "#2AABEE") } },
      { name: "کلیک", value: clk, itemStyle: { color: funnelSegmentGradient("#3D95D4", "#177DC7") } },
      { name: "ورود", value: act, itemStyle: { color: funnelSegmentGradient("#1F9B78", "#16866A") } },
    ];
    chart.setOption({
      animationDuration: 600,
      animationEasing: "cubicOut",
      tooltip: {
        trigger: "item",
        textStyle: { fontFamily: FA_FONT },
        formatter(p) {
          return `${p.name}<br/><strong>${formatCountFull(p.value)}</strong><br/><span style="color:${COLORS.muted}">${shareOfImpressions(p.value)} از نمایش</span>`;
        },
      },
      series: [
        {
          type: "funnel",
          left: "6%",
          right: "6%",
          top: 6,
          bottom: 4,
          width: "88%",
          min: 0,
          max: maxVal,
          minSize: "22%",
          maxSize: "100%",
          sort: "descending",
          funnelAlign: "center",
          gap: 3,
          itemStyle: { borderColor: "#fff", borderWidth: 2 },
          label: {
            show: true,
            position: "inside",
            color: "#fff",
            fontFamily: FA_FONT,
            formatter(p) {
              return `{t|${p.name}}\n{v|${formatCountFull(p.value)}}`;
            },
            rich: {
              t: { fontSize: 11, lineHeight: 18 },
              v: { fontSize: 13, fontWeight: 700, lineHeight: 20 },
            },
          },
          data: steps,
        },
      ],
    });
    requestAnimationFrame(() => chart.resize());
    return chart;
  }

  function funnelChart(el, funnel) {
    const chart = init(el);
    if (!chart) return null;
    const imp = funnel.impressions || 0;
    const clk = funnel.clicks || 0;
    const act = funnel.actions || 0;
    if (!imp && !clk && !act) {
      el.innerHTML = '<p class="muted chart-empty">هنوز داده‌ای برای قیف تبدیل نیست.</p>';
      return null;
    }
    const steps = [
      { value: imp, name: "نمایش" },
      { value: clk, name: "کلیک" },
      { value: act, name: "ورود" },
    ];
    const maxVal = Math.max(imp, clk, act, 1);
    chart.setOption({
      color: [COLORS.impressions, COLORS.clicks, COLORS.actions],
      animationDuration: 600,
      tooltip: {
        trigger: "item",
        textStyle: { fontFamily: FA_FONT },
        formatter(p) {
          return `${p.name}<br/><strong>${formatCountFull(p.value)}</strong>`;
        },
      },
      series: [
        {
          type: "funnel",
          left: "10%",
          right: "10%",
          top: 12,
          bottom: 8,
          min: 0,
          max: maxVal,
          sort: "descending",
          gap: 8,
          itemStyle: {
            borderColor: "#fff",
            borderWidth: 2,
          },
          label: {
            show: true,
            position: "inside",
            color: "#fff",
            fontFamily: FA_FONT,
            fontSize: 12,
            formatter(p) {
              return `${p.name}\n${formatCountFull(p.value)}`;
            },
          },
          data: steps,
        },
      ],
    });
    global.addEventListener("resize", () => chart.resize());
    return chart;
  }

  function portfolioChart(el, data) {
    return performanceChart(el, data, {
      compact: true,
      portfolio: true,
      grid: { bottom: 48, top: 32, left: 8, right: 8 },
    });
  }

  global.TMADSCharts = {
    performanceChart,
    spendChart,
    funnelChart,
    conversionFunnelChart,
    portfolioChart,
    slicePeriodData,
    sliceHasSignal,
    suggestChartRangeDays,
  };

  /** صف/init بعد از آماده‌شدن echarts + TMADSCharts (بدون وابستگی به defer) */
  global.tmadsRunWhenReady = function tmadsRunWhenReady(fn, maxAttempts) {
    const limit = maxAttempts || 80;
    let attempts = 0;
    function tick() {
      attempts += 1;
      if (global.TMADSCharts && global.echarts) {
        try {
          fn();
        } catch (err) {
          console.error("TMADSCharts init failed", err);
        }
        return;
      }
      if (attempts < limit) {
        setTimeout(tick, 40);
      }
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", tick);
    } else {
      tick();
    }
  };
})(window);
