import React, { useState, useRef, useEffect, useMemo } from 'react';
import { 
  MapPin, 
  ChevronDown, 
  Sparkles, 
  Leaf, 
  Flame, 
  Info,
  Heart,
  Home,
  Bell,
  Settings,
  Search,
  AlertCircle,
  Globe,
  Clock,
  ArrowLeft,
  Send,
  MessageCircle
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// --- Utils ---
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- I18n ---
const translations = {
  en: {
    home: "Home",
    alerts: "Alerts",
    settings: "Settings",
    breakfast: "Breakfast",
    lunch: "Lunch",
    dinner: "Dinner",
    aiInsight: "AI Daily Insight",
    aiTitle: "Optimal Intake: ",
    aiTitleHighlight: "High Protein",
    aiDesc: "Based on your muscle-building goals, we recommend the Pan-seared Salmon for lunch. Note: Peanuts detected in Hall 2, items hidden for your safety.",
    clickToChat: "Click to chat with AI",
    protein: "Protein",
    carbs: "Carbs",
    fat: "Fat",
    // Tags
    vegan: "Vegan",
    vegetarian: "Vegetarian",
    spicy: "Spicy",
    highProtein: "High Protein",
    lowCalorie: "Low Calorie",
    kosher: "Kosher",
    halal: "Halal",
    sharedOil: "Fried in Shared Oil",
    // Allergens
    glutenFree: "Gluten-free",
    dairy: "Dairy",
    alcohol: "Alcohol",
    soy: "Soy",
    egg: "Egg",
    coconut: "Coconut",
    treeNuts: "Tree Nuts",
    sesame: "Sesame",
    fish: "Fish",
    shellfish: "Shellfish",
    // UI
    notifTitle: "Notification Settings",
    allowBanner: "Allow Banner Notifications",
    mealTimes: "Meal Reminder Times",
    prefTitle: "Dietary Preferences",
    allergensTitle: "Allergens",
    favDishes: "Saved Dishes",
    favHall: "Favorite Dining Hall",
    aiPush: "AI Smart Recommendation",
    aiPushDesc: "Auto-select hall based on preferences",
    foodPrefs: "Dietary Preferences",
    allCampus: "All Campus",
    hall1: "Dining Hall 1 (Qinyuan)",
    hall2: "Dining Hall 2 (Xiyuan)",
    noFavs: "No saved dishes yet.",
    emptyMenu: "No menu data available.",
    loadingMenu: "Loading today's menu...",
    loadMenuFailed: "Failed to load today's menu.",
    bottomEnd: "~ End of list ~",
    searchPlaceholder: "Search for dishes...",
    searchResults: "Search Results",
    cancel: "Cancel",
    // Chat
    chatTitle: "AI Nutrition Assistant",
    chatPlaceholder: "E.g., I want something light and seafood...",
    chatEmptyMsg: "How can I help you adjust your diet today?",
    chatRecPrefix: "I found this matching your request:"
  },
  zh: {
    home: "首页",
    alerts: "提醒",
    settings: "偏好",
    breakfast: "早餐",
    lunch: "午餐",
    dinner: "晚餐",
    aiInsight: "AI 每日洞察",
    aiTitle: "今日宜摄入 ",
    aiTitleHighlight: "优质蛋白",
    aiDesc: "根据你设定的增肌目标，午餐推荐选择「香煎三文鱼配时蔬」。注意：今日二食堂部分菜品含花生，已为你屏蔽。",
    clickToChat: "点击与 AI 助手对话",
    protein: "蛋白",
    carbs: "碳水",
    fat: "脂肪",
    // Tags
    vegan: "纯素",
    vegetarian: "蛋奶素",
    spicy: "微辣",
    highProtein: "高蛋白",
    lowCalorie: "低热量",
    kosher: "犹太洁食",
    halal: "清真",
    sharedOil: "共用油炸",
    // Allergens
    glutenFree: "麸质",
    dairy: "乳制品",
    alcohol: "酒精",
    soy: "大豆",
    egg: "蛋类",
    coconut: "椰子",
    treeNuts: "坚果",
    sesame: "芝麻",
    fish: "鱼类",
    shellfish: "甲壳类",
    // UI
    notifTitle: "提醒设置",
    allowBanner: "允许横幅通知",
    mealTimes: "就餐提醒时间",
    prefTitle: "饮食偏好设置",
    allergensTitle: "过敏原",
    favDishes: "已收藏的菜品",
    favHall: "最喜欢的食堂",
    aiPush: "AI 智能推荐",
    aiPushDesc: "根据偏好与收藏自动推送食堂",
    foodPrefs: "饮食偏好标签",
    allCampus: "全部校区",
    hall1: "第一食堂 (沁园)",
    hall2: "第二食堂 (熙园)",
    noFavs: "暂无收藏的菜品",
    emptyMenu: "暂无菜单数据",
    loadingMenu: "正在加载今日菜单...",
    loadMenuFailed: "今日菜单加载失败",
    bottomEnd: "~ 已到底部 ~",
    searchPlaceholder: "搜索菜品...",
    searchResults: "搜索结果",
    cancel: "取消",
    // Chat
    chatTitle: "AI 营养助手",
    chatPlaceholder: "例如：想吃点清淡少油腻的海鲜...",
    chatEmptyMsg: "今天想吃点什么？我可以为你个性化推荐。",
    chatRecPrefix: "为你找到符合要求的菜品："
  }
};

type Lang = 'en' | 'zh';
type MealTab = 'breakfast' | 'lunch' | 'dinner';
type HallId = 'hall1' | 'hall2';

type Macronutrients = {
  protein: number;
  carbs: number;
  fat: number;
};

type DietaryTag = 'vegan' | 'vegetarian' | 'spicy' | 'high-protein' | 'low-calorie' | 'kosher' | 'halal' | 'shared-oil';
type AllergenTag = 'gluten-free' | 'dairy' | 'alcohol' | 'soy' | 'egg' | 'coconut' | 'tree-nuts' | 'sesame' | 'fish' | 'shellfish';

type MenuItem = {
  id: string;
  name: { en: string; zh: string };
  calories: number;
  macros: Macronutrients;
  tags: DietaryTag[];
  allergens: AllergenTag[];
  hallId: HallId;
  externalLocationName: string | null;
  stationName: string | null;
  mealSlot: MealTab;
};

type BackendMenuItem = {
  id: string;
  name_en: string;
  name_zh: string;
  calories: number;
  macros: Macronutrients;
  tags: string[];
  allergens: string[];
  hall_id: HallId;
  external_location_name?: string | null;
  station_name?: string | null;
  meal_slot: MealTab;
};

type BackendMenuListResponse = {
  items: BackendMenuItem[];
  total: number;
};

const normalizeBaseUrl = (value: string | undefined): string => (value ?? '').trim().replace(/\/$/, '');

const isAbsoluteHttpUrl = (value: string): boolean => {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
};

const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL as string | undefined);
const MENUS_API_URL = isAbsoluteHttpUrl(API_BASE_URL) ? `${API_BASE_URL}/api/v1/menus` : null;

const DIETARY_TAGS: DietaryTag[] = [
  'vegan',
  'vegetarian',
  'spicy',
  'high-protein',
  'low-calorie',
  'kosher',
  'halal',
  'shared-oil',
];

const ALLERGEN_TAGS: AllergenTag[] = [
  'gluten-free',
  'dairy',
  'alcohol',
  'soy',
  'egg',
  'coconut',
  'tree-nuts',
  'sesame',
  'fish',
  'shellfish',
];

const isDietaryTag = (value: string): value is DietaryTag => DIETARY_TAGS.includes(value as DietaryTag);
const isAllergenTag = (value: string): value is AllergenTag => ALLERGEN_TAGS.includes(value as AllergenTag);

const getHallDisplayLabel = (item: Pick<MenuItem, 'externalLocationName' | 'hallId'>): string =>
  item.externalLocationName?.trim() || item.hallId;

const getStationDisplayLabel = (item: Pick<MenuItem, 'stationName'>): string =>
  item.stationName?.trim() || 'Unassigned Station';

const normalizeText = (value: string): string => value.trim().toLowerCase();

const DEBUG_STATION_RULES = ['1', 'true', 'yes'].includes(
  String(import.meta.env.VITE_DEBUG_STATION_RULES ?? '')
    .trim()
    .toLowerCase()
);

const itemMatchesExactName = (item: Pick<MenuItem, 'name'>, targetName: string): boolean => {
  const target = normalizeText(targetName);
  return normalizeText(item.name.en) === target || normalizeText(item.name.zh) === target;
};

type StationRuleType = 'show_all' | 'hide' | 'summary_only' | 'custom_station' | 'filtered_show_all';
type StationPredicate = (item: MenuItem) => boolean;

type StationDisplayRule = {
  type: StationRuleType;
  keepItems?: string[];
  excludeItems?: string[];
  predicate?: StationPredicate;
};

const ivyGreensSummaryPredicate: StationPredicate = (item) => {
  const value = `${item.name.en} ${item.name.zh}`.toLowerCase();
  const hasIvy = value.includes('ivy');
  const hasAllowedProtein = value.includes('chicken') || value.includes('salmon') || value.includes('steak');
  return hasIvy && hasAllowedProtein;
};

const josMeltSummaryPredicate: StationPredicate = (item) => {
  const value = `${item.name.en} ${item.name.zh}`.toLowerCase();
  return value.includes("jo's bar") || value.includes('jos bar') || (value.includes("jo's") && value.includes('bar'));
};

const vwActionStationPredicate: StationPredicate = (item) =>
  item.name.en.trim().toLowerCase().startsWith('vw-');

const vwPancakeBarPredicate: StationPredicate = (item) => {
  const value = `${item.name.en} ${item.name.zh}`.toLowerCase();
  return value.includes('pancake') || value.includes('pancakes');
};

const sharpeSaladSummaryPredicate: StationPredicate = (item) => {
  const value = `${item.name.en} ${item.name.zh}`.toLowerCase();
  return value.includes('salad bar') && (value.includes('sharpe') || value.includes('ratty'));
};

const sharpeHalalLunchPredicate: StationPredicate = (item) => {
  const value = `${item.name.en} ${item.name.zh}`.toLowerCase();
  return value.includes('chicken') || value.includes('potato') || value.includes('beef') || value.includes('rice');
};

const sharpeHalalDinnerPredicate: StationPredicate = (item) => {
  const value = `${item.name.en} ${item.name.zh}`.toLowerCase();
  return value.includes('chicken') || value.includes('potato');
};

const hallDisplayRules: Record<string, Record<string, StationDisplayRule>> = {
  Andrews: {
    'Deli 11a-3p': { type: 'show_all' },
    'Hot Sandwich 11a-3p': { type: 'show_all' },
    'Breakfast Sandwiches 11a-3p': { type: 'show_all' },
    'Wok 11a-3p': { type: 'custom_station' },
    'Wok 3:30p-9p': { type: 'custom_station' },
    'Wok Dinner 4p-8:30p': { type: 'custom_station' },
    'Sandwich Bar - Served 11am - 3pm': { type: 'summary_only', keepItems: ['Deli Andrews'] },
    'Sandwich Bar - Served 3:30p-8p': { type: 'summary_only', keepItems: ['Deli Andrews'] },
    'Salad Bar - Served 11am -3pm': { type: 'summary_only', keepItems: ['Salad Bar Andrews'] },
    'Condiment Station': { type: 'hide' },
    "Za'atar Salmon 3:30p-9p": { type: 'summary_only', keepItems: ['Roasted Potato Wedges', "Za'atar Salmon"] },
    'Wing Bar 3:30p-9p': { type: 'summary_only', keepItems: ['Buffalo Wings'] },
    'Pizza 11a-3p': { type: 'summary_only', keepItems: ['Taco Bar'] },
    'Burrito 11a-3p': { type: 'summary_only', keepItems: ['Burrito Bowl'] },
    'Granola Bowl 11a-3p': { type: 'summary_only', keepItems: ['Granola Bowl'] },
  },
  Blueroom: {
    'Lunch Hot Sandwich 11a-3p': { type: 'show_all' },
    Pastry: { type: 'hide' },
    'Breakfast Sandwiches-Served 8a-10:30a': { type: 'show_all' },
    'Bagel Bar - Served 8a-10:30 am': { type: 'summary_only', keepItems: ['Bagel Bar'] },
    'Yogurt Bar - Served 8a-10:30 am': { type: 'custom_station' },
    'Sandwich Bar - Served 11am - 3pm': { type: 'summary_only', keepItems: ['Deli Blue Room'] },
    'Salad Bar - Served 11am -3pm': { type: 'summary_only', keepItems: ['Salad Bar Blue Room'] },
    'Soup - Served 11am-3pm': { type: 'show_all' },
  },
  'Ivy Room': {
    'Grab and Go': { type: 'show_all' },
    Smoothie: { type: 'hide' },
    'Greens, Lunch': { type: 'summary_only', predicate: ivyGreensSummaryPredicate },
    Deli: { type: 'hide' },
    'Dinner Comforts': { type: 'show_all' },
  },
  "Josiah's": {
    'Salad Bar 6pm-12am': { type: 'summary_only', keepItems: ['Salad Bar'] },
    'Grill 6am-2am': { type: 'show_all' },
    Sweets: { type: 'show_all' },
    'Melt 6pm-11pm': { type: 'summary_only', predicate: josMeltSummaryPredicate },
    'Milkshake 6pm-11pm': { type: 'hide' },
    'Condiment Station': { type: 'hide' },
  },
  'School of Engineering': {
    '*': { type: 'hide' },
  },
  'Sharpe Refectory': {
    'Greens, Breakfast': { type: 'summary_only', keepItems: ['Breakfast - Fruit Bar', 'Breakfast - Yogurt Bar'] },
    'Greens, Lunch': {
      type: 'summary_only',
      keepItems: ['Salad Bar Sharpe', 'Sharpe Salad Bar', 'Ratty Salad Bar'],
      predicate: sharpeSaladSummaryPredicate,
    },
    'Salad Bar': {
      type: 'summary_only',
      keepItems: ['Salad Bar Sharpe', 'Sharpe Salad Bar', 'Ratty Salad Bar'],
      predicate: sharpeSaladSummaryPredicate,
    },
    'Breakfast Comforts': { type: 'hide' },
    'Breakfast Sides': { type: 'hide' },
    'Sweets Breakfast': { type: 'hide' },
    'Oatmeal Bar': { type: 'hide' },
    'Omelet Bar': { type: 'summary_only', keepItems: ['Sharpe Omelet Bar'] },
    Soups: { type: 'show_all' },
    'Lunch Comforts': { type: 'show_all' },
    Harvest: { type: 'hide' },
    'Halal Lunch': {
      type: 'summary_only',
      predicate: sharpeHalalLunchPredicate,
    },
    'Halal Dinner': {
      type: 'summary_only',
      predicate: sharpeHalalDinnerPredicate,
    },
    Southwest: { type: 'hide' },
    Pizza: { type: 'show_all' },
    Pasta: { type: 'summary_only', keepItems: ['MDR-Pasta Bar'] },
    'Allergen Aware': { type: 'hide' },
    Grill: { type: 'hide' },
    Deli: { type: 'hide' },
    'Sweets Lunch': { type: 'show_all' },
    Special: { type: 'hide' },
  },
  'Verney-Woolley': {
    'Breakfast Comforts': { type: 'hide' },
    'Breakfast Sides': { type: 'hide' },
    'Sweets Breakfast': { type: 'show_all' },
    'Oatmeal Bar': { type: 'hide' },
    'Omelet Bar': { type: 'summary_only', keepItems: ['VW Omelet Bar'] },
    'Yogurt Bar - Served 7:30-10:30 am': { type: 'summary_only', keepItems: ['Breakfast - Yogurt Bar'] },
    Waffles: { type: 'summary_only', keepItems: ['VW - Belgium Waffles'] },
    'Pancake Bar': { type: 'summary_only', predicate: vwPancakeBarPredicate },
    'Condiment Station': { type: 'hide' },
    'French Toast Bar': { type: 'summary_only', keepItems: ['French Toast'] },
    'Salad Bar': { type: 'summary_only', keepItems: ['VW - From The Garden'] },
    'Lunch Comforts': { type: 'show_all' },
    'Lunch Sides': { type: 'show_all' },
    Grill: { type: 'hide' },
    Deli: { type: 'hide' },
    'Sweets Lunch': { type: 'show_all' },
    'Action Station': { type: 'summary_only', predicate: vwActionStationPredicate },
    Pastry: { type: 'summary_only', keepItems: ['VW-Ice Cream Bar'] },
    Accompaniments: { type: 'hide' },
    Special: { type: 'hide' },
  },
};

const hallRuleAliases: Record<string, string> = {
  Andrews: 'Andrews',
  'Andrews Commons': 'Andrews',
  Blueroom: 'Blueroom',
  'Blue Room': 'Blueroom',
  'Blue Room Cafe': 'Blueroom',
  'Ivy Room': 'Ivy Room',
  "Josiah's": "Josiah's",
  'Josiah’s': "Josiah's",
  "Jo's": "Josiah's",
  Josiahs: "Josiah's",
  'School of Engineering': 'School of Engineering',
  'School Of Engineering': 'School of Engineering',
  'Sharpe Refectory': 'Sharpe Refectory',
  'The Ratty': 'Sharpe Refectory',
  'Sharpe Refectory (The Ratty)': 'Sharpe Refectory',
  'Verney-Woolley': 'Verney-Woolley',
  'Verney Woolley': 'Verney-Woolley',
  'Verney Woolley Dining Hall': 'Verney-Woolley',
};

const getHallRuleKey = (hallName: string): string =>
  hallRuleAliases[hallName.trim()] ?? hallName.trim();

const hallHiddenFromSelectorRuleKeys = new Set<string>(['School of Engineering']);
const hallSelectorPreferredLabelsByRuleKey: Record<string, string> = {
  'Verney-Woolley': 'Verney-Woolley',
};

const stationRuleAliases: Record<string, Record<string, string>> = {
  Andrews: {
    'Salad Bar - Served 11am - 3pm': 'Salad Bar - Served 11am -3pm',
    'Salad Bar - Served 11am -3pm': 'Salad Bar - Served 11am -3pm',
    'Wok 3:30p - 9p': 'Wok 3:30p-9p',
    'Wok Dinner 4p - 8:30p': 'Wok Dinner 4p-8:30p',
    "Za'atar Salmon 3:30p - 9p": "Za'atar Salmon 3:30p-9p",
  },
  Blueroom: {
    'Bagel Bar- Served 8a-10:30 am': 'Bagel Bar - Served 8a-10:30 am',
    'Bagel Bar - Served 8a-10:30 am': 'Bagel Bar - Served 8a-10:30 am',
    'Breakfast Sandwiches - Served 8a-10:30a': 'Breakfast Sandwiches-Served 8a-10:30a',
    'Salad Bar - Served 11am - 3pm': 'Salad Bar - Served 11am -3pm',
    'Salad Bar - Served 11am -3pm': 'Salad Bar - Served 11am -3pm',
  },
  "Josiah's": {
    'Melt 6pm - 11pm': 'Melt 6pm-11pm',
    'Melt - 6pm-11pm': 'Melt 6pm-11pm',
  },
  'Sharpe Refectory': {
    'Greens - Lunch': 'Greens, Lunch',
  },
};

const getStationRuleKey = (hallKey: string, stationName: string): string => {
  const trimmed = stationName.trim();
  const aliases = stationRuleAliases[hallKey];
  return aliases?.[trimmed] ?? trimmed;
};

const normalizeMealSlot = (value: string | undefined): MealTab => {
  if (value === 'breakfast' || value === 'lunch' || value === 'dinner') {
    return value;
  }
  return 'lunch';
};

const stationMealSlotOverrides: Record<string, Record<string, MealTab>> = {
  Blueroom: {
    'Bagel Bar - Served 8a-10:30 am': 'breakfast',
    'Breakfast Sandwiches-Served 8a-10:30a': 'breakfast',
    'Yogurt Bar - Served 8a-10:30 am': 'breakfast',
  },
  "Josiah's": {
    '*': 'dinner',
  },
  'Sharpe Refectory': {
    'Dinner Comforts': 'dinner',
    'Dinner Sides': 'dinner',
    'Sweets Dinner': 'dinner',
    'Halal Dinner': 'dinner',
  },
};

const normalizeMealSlotForDisplay = (
  mealSlot: string,
  hallDisplayName: string | null | undefined,
  stationDisplayName: string | null | undefined
): MealTab => {
  const normalizedMealSlot = normalizeMealSlot(mealSlot);
  const hallKey = hallDisplayName ? getHallRuleKey(hallDisplayName) : '';
  const stationName = stationDisplayName?.trim() ?? '';
  const stationKey = getStationRuleKey(hallKey, stationName);
  const stationLower = stationKey.toLowerCase();

  const hallOverrides = stationMealSlotOverrides[hallKey];
  if (hallOverrides?.[stationKey]) {
    return hallOverrides[stationKey];
  }
  if (hallOverrides?.['*']) {
    return hallOverrides['*'];
  }

  if (hallKey === 'Sharpe Refectory') {
    if (stationLower.includes('breakfast')) {
      return 'breakfast';
    }
    if (
      stationLower.includes('dinner') ||
      stationLower.includes('supper') ||
      stationLower.includes('3:30p-9p')
    ) {
      return 'dinner';
    }
  }

  return normalizedMealSlot;
};

const isBlueRoomPastryStation = (item: Pick<MenuItem, 'externalLocationName' | 'hallId' | 'stationName'>): boolean => {
  const hallKey = getHallRuleKey(getHallDisplayLabel(item));
  if (hallKey !== 'Blueroom') return false;
  const stationKey = getStationRuleKey(hallKey, getStationDisplayLabel(item));
  return stationKey === 'Pastry';
};

const shouldIncludeItemForMealTab = (item: MenuItem, tab: MealTab): boolean => {
  if (item.mealSlot === tab) return true;

  // Blue Room pastry is intentionally visible in both breakfast and lunch tabs.
  if (isBlueRoomPastryStation(item) && (tab === 'breakfast' || tab === 'lunch')) {
    return true;
  }

  return false;
};

const getItemDisplayName = (item: MenuItem, lang: Lang): string => {
  const rawName = item.name[lang];

  // Keep raw matching data intact; only remove "Retail" from Blue Room pastry display text.
  if (isBlueRoomPastryStation(item)) {
    return rawName.replace(/\bretail\b/gi, '').replace(/\s{2,}/g, ' ').trim();
  }

  return rawName;
};

const defaultStationRule: StationDisplayRule = { type: 'show_all' };

const getStationRule = (hallName: string, stationName: string): StationDisplayRule => {
  const hallKey = getHallRuleKey(hallName);
  const stationKey = getStationRuleKey(hallKey, stationName);
  if (DEBUG_STATION_RULES && stationKey !== stationName.trim()) {
    console.debug('[station-rule-alias]', {
      hallName,
      hallKey,
      stationName,
      stationKey,
    });
  }
  const hallRules = hallDisplayRules[hallKey];
  if (!hallRules) return defaultStationRule;
  return hallRules[stationKey] ?? hallRules['*'] ?? defaultStationRule;
};

const applySummaryOnlyRule = (items: MenuItem[], rule: StationDisplayRule): MenuItem[] =>
  items.filter((item) => {
    const keepMatched = (rule.keepItems ?? []).some((name) => itemMatchesExactName(item, name));
    const predicateMatched = rule.predicate ? rule.predicate(item) : false;
    return keepMatched || predicateMatched;
  });

const applyFilteredShowAllRule = (items: MenuItem[], rule: StationDisplayRule): MenuItem[] =>
  items.filter((item) => !(rule.excludeItems ?? []).some((name) => itemMatchesExactName(item, name)));

type StationRenderSection =
  | {
      kind: 'items';
      key: string;
      hallName: string;
      stationName: string;
      items: MenuItem[];
    }
  | {
      kind: 'custom_station';
      key: string;
      hallName: string;
      stationName: string;
      rawItems: MenuItem[];
    };

const buildStationSections = (items: MenuItem[]): StationRenderSection[] => {
  const grouped = new Map<string, { hallName: string; stationName: string; items: MenuItem[] }>();

  for (const item of items) {
    const hallName = getHallDisplayLabel(item);
    const stationName = getStationDisplayLabel(item);
    const key = `${hallName}:::${stationName}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.items.push(item);
    } else {
      grouped.set(key, { hallName, stationName, items: [item] });
    }
  }

  const sections: StationRenderSection[] = [];

  for (const group of grouped.values()) {
    const rule = getStationRule(group.hallName, group.stationName);
    const mealSlotLabel = Array.from(new Set(group.items.map((item) => item.mealSlot))).join(',');
    const rawCount = group.items.length;

    if (rule.type === 'hide') {
      if (DEBUG_STATION_RULES) {
        console.debug('[station-rule]', {
          hallName: group.hallName,
          stationName: group.stationName,
          mealSlot: mealSlotLabel,
          ruleType: rule.type,
          keptItemCount: 0,
          rawItemCount: rawCount,
        });
      }
      continue;
    }

    if (rule.type === 'custom_station') {
      if (DEBUG_STATION_RULES) {
        console.debug('[station-rule]', {
          hallName: group.hallName,
          stationName: group.stationName,
          mealSlot: mealSlotLabel,
          ruleType: rule.type,
          keptItemCount: rawCount,
          rawItemCount: rawCount,
        });
      }
      sections.push({
        kind: 'custom_station',
        key: `${group.hallName}:::${group.stationName}`,
        hallName: group.hallName,
        stationName: group.stationName,
        rawItems: group.items,
      });
      continue;
    }

    let stationItems = group.items;
    if (rule.type === 'summary_only') {
      stationItems = applySummaryOnlyRule(group.items, rule);
    } else if (rule.type === 'filtered_show_all') {
      stationItems = applyFilteredShowAllRule(group.items, rule);
    }

    if (stationItems.length === 0) {
      if (DEBUG_STATION_RULES) {
        console.debug('[station-rule]', {
          hallName: group.hallName,
          stationName: group.stationName,
          mealSlot: mealSlotLabel,
          ruleType: rule.type,
          keptItemCount: 0,
          rawItemCount: rawCount,
        });
      }
      continue;
    }

    if (DEBUG_STATION_RULES) {
      console.debug('[station-rule]', {
        hallName: group.hallName,
        stationName: group.stationName,
        mealSlot: mealSlotLabel,
        ruleType: rule.type,
        keptItemCount: stationItems.length,
        rawItemCount: rawCount,
      });
    }

    sections.push({
      kind: 'items',
      key: `${group.hallName}:::${group.stationName}`,
      hallName: group.hallName,
      stationName: group.stationName,
      items: stationItems,
    });
  }

  return sections;
};

const toMenuItem = (item: BackendMenuItem): MenuItem => ({
  id: item.id,
  name: {
    en: item.name_en,
    zh: item.name_zh || item.name_en,
  },
  calories: Number.isFinite(item.calories) ? item.calories : 0,
  macros: {
    protein: Number(item.macros?.protein ?? 0),
    carbs: Number(item.macros?.carbs ?? 0),
    fat: Number(item.macros?.fat ?? 0),
  },
  tags: (item.tags ?? []).filter(isDietaryTag),
  allergens: (item.allergens ?? []).filter(isAllergenTag),
  hallId: item.hall_id,
  externalLocationName: item.external_location_name ?? null,
  stationName: item.station_name ?? null,
  mealSlot: normalizeMealSlotForDisplay(item.meal_slot, item.external_location_name, item.station_name),
});

type ChatMessage = {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  recommendedDishId?: string;
};

// --- Components ---

const ToggleSwitch = ({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) => (
  <label className="relative inline-flex items-center cursor-pointer shrink-0">
    <input type="checkbox" className="sr-only peer" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
  </label>
);

const DietTagBadge = ({ tag, lang }: { tag: DietaryTag; lang: Lang }) => {
  const t = translations[lang];
  const getStyle = (tag: DietaryTag) => {
    switch (tag) {
      case 'vegan': return "bg-green-100 text-green-700";
      case 'vegetarian': return "bg-emerald-100 text-emerald-700";
      case 'spicy': return "bg-red-100 text-red-700";
      case 'high-protein': return "bg-blue-100 text-blue-700";
      case 'low-calorie': return "bg-teal-100 text-teal-700";
      case 'kosher': return "bg-indigo-100 text-indigo-700";
      case 'halal': return "bg-cyan-100 text-cyan-700";
      case 'shared-oil': return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <span className={cn("inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded", getStyle(tag))}>
      {tag === 'vegan' && <Leaf className="w-2.5 h-2.5" />}
      {tag === 'spicy' && <Flame className="w-2.5 h-2.5" />}
      {tag === 'kosher' && <span className="font-bold">K</span>}
      {tag === 'halal' && <span className="font-bold">H</span>}
      {lang === 'en' ? 
        t[tag.replace(/-./g, x => x[1].toUpperCase()) as keyof typeof t] : 
        t[tag.replace(/-./g, x => x[1].toUpperCase()) as keyof typeof t]}
    </span>
  );
};

const AllergenBadge = ({ allergen, lang }: { allergen: AllergenTag; lang: Lang }) => {
  const t = translations[lang];
  const camelKey = allergen.replace(/-./g, x => x[1].toUpperCase()) as keyof typeof t;
  
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-rose-50 text-rose-600 border border-rose-100/50">
      <AlertCircle className="w-2.5 h-2.5" />
      {t[camelKey]}
    </span>
  );
};

const MacroBar = ({ label, value, colorClass, max = 100 }: { label: string; value: number; colorClass: string; max?: number }) => {
  const percentage = Math.min((value / max) * 100, 100);
  return (
    <div className="flex flex-col gap-0.5 w-full">
      <div className="flex justify-between items-center text-[10px] text-gray-500 font-medium">
        <span>{label}</span>
        <span>{value}g</span>
      </div>
      <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", colorClass)} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
};

const MenuItemCard = ({ 
  item, 
  lang,
  isFav,
  onToggleFav,
  compact = false
}: { 
  item: MenuItem; 
  lang: Lang;
  isFav: boolean;
  onToggleFav: (id: string) => void;
  compact?: boolean;
}) => {
  const t = translations[lang];

  return (
    <div className={cn(
      "bg-white rounded-2xl shadow-sm border border-gray-100/50 active:scale-[0.99] transition-transform",
      compact ? "p-3 mb-1" : "p-4 mb-3"
    )}>
      <div className="flex justify-between items-start mb-2">
        <div className="pr-4">
          <div className="flex items-center gap-2 mb-1.5">
            <h3 className={cn("font-bold text-gray-900 leading-tight", compact ? "text-sm" : "text-base")}>
              {getItemDisplayName(item, lang)}
            </h3>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium whitespace-nowrap">
              {getHallDisplayLabel(item)}
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {item.tags.map(tag => <DietTagBadge key={tag} tag={tag} lang={lang} />)}
            {item.allergens.map(allergen => <AllergenBadge key={allergen} allergen={allergen} lang={lang} />)}
          </div>
        </div>
        <div className="flex flex-col items-end shrink-0">
          <span className={cn("font-black text-gray-900 tracking-tight", compact ? "text-base" : "text-lg")}>{item.calories}</span>
          <span className="text-[9px] text-gray-400 font-medium">kcal</span>
        </div>
      </div>

      <div className={cn("mt-3 pt-3 border-t border-gray-50 flex items-end justify-between gap-4", compact && "mt-2 pt-2")}>
        {/* Macros */}
        <div className="flex-1 grid grid-cols-3 gap-2">
          <MacroBar label={t.protein} value={item.macros.protein} colorClass="bg-blue-400" max={50} />
          <MacroBar label={t.carbs} value={item.macros.carbs} colorClass="bg-amber-400" max={100} />
          <MacroBar label={t.fat} value={item.macros.fat} colorClass="bg-red-400" max={50} />
        </div>

        {/* Actions - Only Favorite remaining */}
        <div className="flex items-center gap-1 shrink-0 pl-2">
          <button 
            onClick={() => onToggleFav(item.id)}
            className={cn("rounded-full transition-colors", 
              compact ? "p-1.5" : "p-2",
              isFav ? "text-rose-500 bg-rose-50" : "text-gray-400 bg-gray-50"
            )}
          >
            <Heart className={cn(compact ? "w-4 h-4" : "w-5 h-5", isFav && "fill-current")} />
          </button>
        </div>
      </div>
    </div>
  );
};

// Placeholder card for configurable stations (e.g., bowl/salad/yogurt builders).
// Future work: expand to interactive selection and nutrition aggregation from `rawItems`.
const CustomStationCard = ({
  stationName,
  rawCount,
}: {
  stationName: string;
  rawCount: number;
}) => (
  <div className="bg-white rounded-2xl shadow-sm border border-dashed border-indigo-200/70 p-4 mb-3">
    <div className="flex items-center justify-between mb-1.5">
      <h3 className="font-semibold text-gray-900">{stationName}</h3>
      <span className="text-[10px] font-semibold uppercase tracking-wide text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full">
        Customizable
      </span>
    </div>
    <p className="text-sm text-gray-600 leading-relaxed">
      This station is customizable. Ingredient-level builder UX will be added in a future release.
    </p>
    <p className="mt-2 text-[11px] text-gray-400">
      {rawCount} raw options available
    </p>
  </div>
);


export default function App() {
  // Global State
  const [lang, setLang] = useState<Lang>('en');
  const t = translations[lang];
  const [mainTab, setMainTab] = useState<'home' | 'alerts' | 'settings'>('home');
  const [mealTab, setMealTab] = useState<MealTab>('lunch');
  const [favorites, setFavorites] = useState<string[]>([]);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [isMenuLoading, setIsMenuLoading] = useState(true);
  const [menuLoadError, setMenuLoadError] = useState(false);
  
  // Location & Search State
  const [selectedLocation, setSelectedLocation] = useState<string>('all');
  const [isLocationMenuOpen, setIsLocationMenuOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchInputRef = useRef<HTMLInputElement>(null);

  // AI Chat State
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Notification State
  const [allowNotifications, setAllowNotifications] = useState(false);
  const [times, setTimes] = useState({ breakfast: '07:30', lunch: '11:45', dinner: '17:30' });

  // Preference State
  const [favHall, setFavHall] = useState('hall1');
  const [aiAutoPush, setAiAutoPush] = useState(true);
  const [prefTags, setPrefTags] = useState<DietaryTag[]>(['high-protein', 'low-calorie']);
  const [allergenTags, setAllergenTags] = useState<AllergenTag[]>(['gluten-free']);

  const toggleFavorite = (id: string) => {
    setFavorites(prev => prev.includes(id) ? prev.filter(fid => fid !== id) : [...prev, id]);
  };

  const togglePrefTag = (tag: DietaryTag) => {
    setPrefTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]);
  };
  
  const toggleAllergenTag = (tag: AllergenTag) => {
    setAllergenTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]);
  };

  const hallOptions = useMemo(() => {
    const byHallKey = new Map<string, string>();

    for (const item of menuItems) {
      const rawLabel = getHallDisplayLabel(item);
      const hallKey = getHallRuleKey(rawLabel);

      if (hallHiddenFromSelectorRuleKeys.has(hallKey)) {
        continue;
      }

      const preferredLabel = hallSelectorPreferredLabelsByRuleKey[hallKey];
      const candidateLabel = preferredLabel ?? rawLabel;
      const existing = byHallKey.get(hallKey);
      if (!existing) {
        byHallKey.set(hallKey, candidateLabel);
        continue;
      }

      if (!preferredLabel && existing === item.hallId) {
        byHallKey.set(hallKey, rawLabel);
      }
    }

    return Array.from(byHallKey.values()).sort((a, b) => a.localeCompare(b));
  }, [menuItems]);

  const handleLocationSelect = (loc: string) => {
    setSelectedLocation(loc);
    setIsLocationMenuOpen(false);
  };

  useEffect(() => {
    if (selectedLocation !== 'all' && !hallOptions.includes(selectedLocation)) {
      setSelectedLocation('all');
    }
  }, [hallOptions, selectedLocation]);

  useEffect(() => {
    let cancelled = false;

    const fetchTodayMenus = async () => {
      setIsMenuLoading(true);
      setMenuLoadError(false);

      try {
        if (!MENUS_API_URL) {
          throw new Error('VITE_API_BASE_URL is missing or invalid. It must be an absolute http(s) URL.');
        }

        const response = await fetch(MENUS_API_URL, {
          headers: {
            Accept: 'application/json',
          },
        });
        if (!response.ok) {
          throw new Error(`Menu API request failed: ${response.status}`);
        }

        const payload = (await response.json()) as Partial<BackendMenuListResponse>;
        if (!payload || !Array.isArray(payload.items)) {
          throw new Error('Menu API response is invalid');
        }

        const normalizedItems = payload.items.map(toMenuItem);
        if (cancelled) return;

        setMenuItems(normalizedItems);
        setFavorites((prev) => prev.filter((id) => normalizedItems.some((item) => item.id === id)));
      } catch (error) {
        console.error('Failed to fetch menus:', error);
        if (cancelled) return;
        setMenuItems([]);
        setMenuLoadError(true);
      } finally {
        if (!cancelled) {
          setIsMenuLoading(false);
        }
      }
    };

    void fetchTodayMenus();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (isSearching && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isSearching]);

  // AI Chat Logic
  useEffect(() => {
    if (isChatOpen && chatMessages.length === 0) {
      const initialRecommendationId =
        menuItems.find((item) => item.mealSlot === 'lunch')?.id ?? menuItems[0]?.id;
      // Initialize with the first AI insight
      setChatMessages([
        {
          id: '1',
          sender: 'ai',
          text: t.aiDesc,
          recommendedDishId: initialRecommendationId,
        },
      ]);
    }
  }, [isChatOpen, chatMessages.length, t.aiDesc, menuItems]);

  useEffect(() => {
    // Auto-scroll to bottom of chat
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages, isChatOpen]);

  const handleSendChat = () => {
    if (!chatInput.trim()) return;

    const userText = chatInput.trim();
    const newUserMsg: ChatMessage = { id: Date.now().toString(), sender: 'user', text: userText };
    setChatMessages(prev => [...prev, newUserMsg]);
    setChatInput('');

    const pickRecommendedItem = (predicate: (item: MenuItem) => boolean): MenuItem | undefined => (
      menuItems.find((item) => item.mealSlot === mealTab && predicate(item))
      ?? menuItems.find(predicate)
      ?? menuItems.find((item) => item.mealSlot === mealTab)
      ?? menuItems[0]
    );

    // Lightweight keyword recommendation from today's menu.
    setTimeout(() => {
      const lower = userText.toLowerCase();
      let aiText = '';
      let recommended: MenuItem | undefined;

      if (lower.includes('海鲜') || lower.includes('seafood') || lower.includes('鱼') || lower.includes('fish')) {
        aiText = lang === 'zh' ? '为你找到这款高蛋白海鲜，清淡不油腻：' : 'Found this high-protein seafood option, light and not greasy:';
        recommended = pickRecommendedItem(item => item.allergens.includes('fish') || item.allergens.includes('shellfish'));
      } else if (lower.includes('少油') || lower.includes('light') || lower.includes('清淡') || lower.includes('减肥')) {
        aiText = lang === 'zh' ? '没问题，这道低卡清淡的菜品很适合你：' : 'No problem, this light and low-calorie dish is perfect for you:';
        recommended = pickRecommendedItem(item => item.tags.includes('low-calorie') || item.calories <= 320);
      } else if (lower.includes('辣') || lower.includes('spicy')) {
        aiText = lang === 'zh' ? '安排！这款微辣的菜品保证让你胃口大开：' : 'Got it! This spicy dish is very appetizing:';
        recommended = pickRecommendedItem(item => item.tags.includes('spicy'));
      } else {
        aiText = lang === 'zh' ? '根据你的输入，我为你推荐：' : 'Based on your input, I recommend:';
        recommended = pickRecommendedItem(item => item.tags.includes('high-protein'));
      }

      setChatMessages(prev => [
        ...prev,
        { id: Date.now().toString(), sender: 'ai', text: aiText, recommendedDishId: recommended?.id }
      ]);
    }, 600);
  };

  // Render Views
  const renderHome = () => {
    let currentItems = menuItems;

    // Filter by Search or Meal Tab
    if (isSearching && searchQuery.trim() !== '') {
      const q = searchQuery.toLowerCase();
      currentItems = currentItems.filter(item =>
        item.name.en.toLowerCase().includes(q) ||
        item.name.zh.includes(q)
      );
    } else {
      currentItems = currentItems.filter((item) => shouldIncludeItemForMealTab(item, mealTab));
      currentItems = Array.from(new Map(currentItems.map((item) => [item.id, item])).values());
    }

    // Filter by Location
    if (selectedLocation !== 'all') {
      const selectedHallKey = getHallRuleKey(selectedLocation);
      currentItems = currentItems.filter(
        (item) => getHallRuleKey(getHallDisplayLabel(item)) === selectedHallKey
      );
    }

    const stationSections = buildStationSections(currentItems);
    const renderedCount = stationSections.reduce((count, section) => (
      count + (section.kind === 'items' ? section.items.length : 1)
    ), 0);
    
    return (
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        
        {!isSearching && (
          <>
            {/* AI Insight Hero Card - Now Clickable */}
            <div 
              onClick={() => setIsChatOpen(true)}
              className="mt-2 mb-6 rounded-3xl p-5 bg-gradient-to-br from-indigo-50 via-blue-50/50 to-white border border-indigo-100/50 relative overflow-hidden shadow-sm cursor-pointer hover:shadow-md active:scale-[0.98] transition-all group"
            >
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:scale-110 group-hover:opacity-20 transition-all duration-500">
                <Sparkles className="w-24 h-24 text-indigo-500" />
              </div>
              <div className="relative z-10 flex flex-col gap-3">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-1.5 text-indigo-600 font-semibold text-sm">
                    <Sparkles className="w-4 h-4" />
                    <span>{t.aiInsight}</span>
                  </div>
                  <div className="flex items-center gap-1 text-[10px] text-indigo-400 font-medium bg-indigo-50/50 px-2 py-1 rounded-full border border-indigo-100/50 group-hover:bg-indigo-100 transition-colors">
                    <MessageCircle className="w-3 h-3" />
                    {t.clickToChat}
                  </div>
                </div>
                <h2 className="text-lg font-bold text-gray-900 leading-snug">
                  {t.aiTitle}<span className="text-indigo-600">{t.aiTitleHighlight}</span> 💪
                </h2>
                <p className="text-sm text-gray-600 leading-relaxed line-clamp-2">
                  {t.aiDesc}
                </p>
              </div>
            </div>

            {/* Meal Tabs - Sticky Subheader */}
            <div className="sticky top-0 z-10 bg-gray-50/95 backdrop-blur-sm py-2 mb-4 -mx-1 px-1">
              <div className="flex p-1 bg-gray-200/50 rounded-2xl">
                {(['breakfast', 'lunch', 'dinner'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setMealTab(tab)}
                    className={cn(
                      "flex-1 py-2 text-sm font-semibold rounded-xl transition-all",
                      mealTab === tab 
                        ? "bg-white text-gray-900 shadow-sm" 
                        : "text-gray-500 hover:text-gray-700"
                    )}
                  >
                    {t[tab]}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {isSearching && (
          <div className="py-3 mb-2 flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-500">{t.searchResults}</h2>
            <span className="text-xs text-gray-400">{renderedCount} results</span>
          </div>
        )}

        {/* Menu List */}
        <div className="flex flex-col gap-0 pb-6">
          {isMenuLoading && Array.from({ length: 3 }).map((_, index) => (
            <div key={`loading-${index}`} className="bg-white rounded-2xl shadow-sm border border-gray-100/50 p-4 mb-3 animate-pulse">
              <div className="h-4 w-32 bg-gray-100 rounded mb-3"></div>
              <div className="h-3 w-20 bg-gray-100 rounded mb-4"></div>
              <div className="grid grid-cols-3 gap-2">
                <div className="h-6 bg-gray-100 rounded"></div>
                <div className="h-6 bg-gray-100 rounded"></div>
                <div className="h-6 bg-gray-100 rounded"></div>
              </div>
            </div>
          ))}
          {isMenuLoading && (
            <div className="pb-3 text-center text-xs text-gray-400 font-medium">
              {t.loadingMenu}
            </div>
          )}

          {!isMenuLoading && !menuLoadError && stationSections.map((section) => (
            <div key={section.key} className="mb-1">
              <div className="px-1 pb-1">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                  {section.hallName}
                </p>
                <p className="text-xs font-semibold text-gray-600">{section.stationName}</p>
              </div>
              {section.kind === 'custom_station' ? (
                <CustomStationCard
                  stationName={section.stationName}
                  rawCount={section.rawItems.length}
                />
              ) : (
                section.items.map((item) => (
                  <MenuItemCard
                    key={item.id}
                    item={item}
                    lang={lang}
                    isFav={favorites.includes(item.id)}
                    onToggleFav={toggleFavorite}
                  />
                ))
              )}
            </div>
          ))}

          {!isMenuLoading && menuLoadError && (
            <div className="py-12 text-center text-gray-400 flex flex-col items-center gap-2">
              <Info className="w-8 h-8 opacity-20" />
              <p className="text-sm font-medium">{t.loadMenuFailed}</p>
            </div>
          )}

          {!isMenuLoading && !menuLoadError && stationSections.length === 0 && (
            <div className="py-12 text-center text-gray-400 flex flex-col items-center gap-2">
              <Info className="w-8 h-8 opacity-20" />
              <p className="text-sm font-medium">{t.emptyMenu}</p>
            </div>
          )}
        </div>

        <div className="text-center pt-2 pb-8">
          <p className="text-xs text-gray-400 font-medium tracking-wide">{t.bottomEnd}</p>
        </div>
      </div>
    );
  };

  const renderAlerts = () => (
    // ... Alert rendering logic remains the same
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 pb-12">
      <h2 className="text-xl font-bold text-gray-900 mb-6 px-1">{t.notifTitle}</h2>
      
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100/50 mb-6 flex justify-between items-center">
        <div className="flex flex-col gap-1 pr-4">
          <span className="font-semibold text-gray-900 leading-tight">{t.allowBanner}</span>
        </div>
        <ToggleSwitch checked={allowNotifications} onChange={setAllowNotifications} />
      </div>

      <div className={cn("transition-opacity duration-300", !allowNotifications && "opacity-50 pointer-events-none")}>
        <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 px-1">{t.mealTimes}</h3>
        <div className="bg-white rounded-2xl p-2 shadow-sm border border-gray-100/50 flex flex-col">
          {(['breakfast', 'lunch', 'dinner'] as const).map((meal, idx) => (
            <div key={meal} className={cn("flex justify-between items-center p-4", idx !== 2 && "border-b border-gray-50")}>
              <div className="flex items-center gap-3">
                <Clock className="w-5 h-5 text-indigo-400" />
                <span className="font-medium text-gray-900 capitalize">{t[meal]}</span>
              </div>
              <input 
                type="time" 
                value={times[meal]}
                onChange={(e) => setTimes({...times, [meal]: e.target.value})}
                className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-900 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderSettings = () => {
    // ... Settings rendering logic remains the same
    const favItems = menuItems.filter(item => favorites.includes(item.id));

    return (
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 pb-12">
        <h2 className="text-xl font-bold text-gray-900 mb-6 px-1">{t.prefTitle}</h2>
        
        {/* Dining Hall Prefs */}
        <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 px-1">{t.favHall}</h3>
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100/50 mb-6 flex flex-col gap-4">
          <div className="flex justify-between items-center">
            <div className="flex flex-col gap-1">
              <span className="font-semibold text-gray-900">{t.aiPush}</span>
              <span className="text-xs text-gray-500">{t.aiPushDesc}</span>
            </div>
            <ToggleSwitch checked={aiAutoPush} onChange={setAiAutoPush} />
          </div>
          
          <div className={cn("transition-all duration-300 overflow-hidden", aiAutoPush ? "h-0 opacity-0" : "h-auto opacity-100 pt-3 border-t border-gray-50")}>
            <select 
              value={favHall}
              onChange={(e) => setFavHall(e.target.value)}
              className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-900 focus:ring-2 focus:ring-indigo-500 focus:outline-none appearance-none"
            >
              <option value="hall1">{t.hall1}</option>
              <option value="hall2">{t.hall2}</option>
            </select>
          </div>
        </div>

        {/* Dietary Prefs */}
        <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 px-1">{t.foodPrefs}</h3>
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100/50 mb-6">
          <div className="flex flex-wrap gap-2">
            {DIETARY_TAGS.map(tag => {
              const isSelected = prefTags.includes(tag);
              const camelKey = tag.replace(/-./g, x => x[1].toUpperCase()) as keyof typeof t;
              return (
                <button
                  key={tag}
                  onClick={() => togglePrefTag(tag)}
                  className={cn(
                    "px-3 py-1.5 rounded-xl text-sm font-medium transition-colors border",
                    isSelected 
                      ? "bg-indigo-50 border-indigo-200 text-indigo-700 shadow-sm" 
                      : "bg-gray-50 border-gray-100 text-gray-600 hover:bg-gray-100"
                  )}
                >
                  {t[camelKey]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Allergens */}
        <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 px-1">{t.allergensTitle}</h3>
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100/50 mb-6">
          <p className="text-xs text-gray-400 mb-3">{lang === 'zh' ? '选中的过敏原将在菜单中被标记' : 'Selected allergens will be highlighted in menu'}</p>
          <div className="flex flex-wrap gap-2">
            {ALLERGEN_TAGS.map(tag => {
              const isSelected = allergenTags.includes(tag);
              const camelKey = tag.replace(/-./g, x => x[1].toUpperCase()) as keyof typeof t;
              return (
                <button
                  key={tag}
                  onClick={() => toggleAllergenTag(tag)}
                  className={cn(
                    "px-3 py-1.5 rounded-xl text-sm font-medium transition-colors border",
                    isSelected 
                      ? "bg-rose-50 border-rose-200 text-rose-700 shadow-sm" 
                      : "bg-gray-50 border-gray-100 text-gray-600 hover:bg-gray-100"
                  )}
                >
                  {t[camelKey]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Saved Dishes */}
        <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 px-1">{t.favDishes}</h3>
        <div className="flex flex-col gap-0">
          {favItems.map(item => (
            <MenuItemCard 
              key={item.id} 
              item={item} 
              lang={lang} 
              isFav={true}
              onToggleFav={toggleFavorite}
            />
          ))}
          {favItems.length === 0 && (
            <div className="py-8 text-center text-gray-400 bg-white rounded-2xl border border-gray-100/50 border-dashed">
              <Heart className="w-6 h-6 opacity-20 mx-auto mb-2" />
              <p className="text-sm">{t.noFavs}</p>
            </div>
          )}
        </div>
      </div>
    );
  };

  const getHeaderTitle = () => {
    if (selectedLocation === 'all') return t.allCampus;
    return selectedLocation;
  };

  return (
    <div className="min-h-screen bg-gray-50/50 font-sans flex justify-center relative">
      {/* Mobile Container */}
      <div className="w-full max-w-md bg-gray-50/50 relative shadow-2xl flex flex-col h-screen overflow-hidden ring-1 ring-gray-200/50">
        
        {/* Header - Sticky */}
        <header className="px-5 py-4 bg-white/80 backdrop-blur-md sticky top-0 z-40 flex flex-col gap-3">
          
          {/* Top Bar */}
          {!isSearching ? (
            <div className="flex justify-between items-center relative">
              <button 
                onClick={() => setIsLocationMenuOpen(!isLocationMenuOpen)}
                className="flex items-center gap-1.5 group max-w-[65%]"
              >
                <div className="p-1.5 bg-gray-100 rounded-full group-active:scale-95 transition-transform shrink-0">
                  <MapPin className="w-4 h-4 text-gray-700" />
                </div>
                <span className="font-bold text-base md:text-lg tracking-tight text-gray-900 truncate">
                  {getHeaderTitle()}
                </span>
                <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
              </button>

              <div className="flex items-center gap-2 shrink-0">
                <button 
                  onClick={() => setLang(lang === 'en' ? 'zh' : 'en')}
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-gray-50 border border-gray-100 rounded-full text-xs font-semibold text-gray-600 active:scale-95 transition-transform"
                >
                  <Globe className="w-3.5 h-3.5" />
                  {lang === 'en' ? '中' : 'EN'}
                </button>
                <button 
                  onClick={() => setIsSearching(true)}
                  className="p-2 bg-gray-50 rounded-full text-gray-600 active:scale-95 transition-transform"
                >
                  <Search className="w-5 h-5" />
                </button>
              </div>

              {/* Custom Location Dropdown Overlay */}
              {isLocationMenuOpen && (
                <>
                  <div 
                    className="fixed inset-0 z-30" 
                    onClick={() => setIsLocationMenuOpen(false)}
                  />
                  <div className="absolute top-full left-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-gray-100/50 py-1.5 z-40 animate-in fade-in slide-in-from-top-2 duration-200">
                    <button 
                      onClick={() => handleLocationSelect('all')}
                      className={cn("w-full text-left px-4 py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors", selectedLocation === 'all' ? "text-indigo-600 bg-indigo-50/50" : "text-gray-700")}
                    >
                      {t.allCampus}
                    </button>
                    {hallOptions.map((hallName) => (
                      <button
                        key={hallName}
                        onClick={() => handleLocationSelect(hallName)}
                        className={cn(
                          "w-full text-left px-4 py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors",
                          selectedLocation === hallName ? "text-indigo-600 bg-indigo-50/50" : "text-gray-700"
                        )}
                      >
                        {hallName}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 animate-in fade-in zoom-in-95 duration-200">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  ref={searchInputRef}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={t.searchPlaceholder}
                  className="w-full bg-gray-100/80 border-transparent focus:border-indigo-500 focus:bg-white focus:ring-2 focus:ring-indigo-200 rounded-full pl-9 pr-4 py-2 text-sm text-gray-900 outline-none transition-all"
                />
              </div>
              <button 
                onClick={() => {
                  setIsSearching(false);
                  setSearchQuery('');
                }}
                className="text-sm font-medium text-gray-600 hover:text-gray-900 whitespace-nowrap px-2"
              >
                {t.cancel}
              </button>
            </div>
          )}
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto px-5 pt-2 pb-24 hide-scrollbar">
          {mainTab === 'home' && renderHome()}
          {mainTab === 'alerts' && renderAlerts()}
          {mainTab === 'settings' && renderSettings()}
        </main>

        {/* Bottom Navigation */}
        <nav className="absolute bottom-0 w-full bg-white border-t border-gray-100 px-6 py-3 pb-8 shadow-[0_-10px_40px_-15px_rgba(0,0,0,0.05)] flex justify-between items-center z-30">
          <button 
            onClick={() => setMainTab('home')}
            className={cn("flex flex-col items-center gap-1 p-2 transition-colors", mainTab === 'home' ? "text-indigo-600" : "text-gray-400 hover:text-gray-600")}
          >
            <Home className={cn("w-6 h-6", mainTab === 'home' && "fill-indigo-600/10")} />
            <span className="text-[10px] font-bold">{t.home}</span>
          </button>
          <button 
            onClick={() => setMainTab('alerts')}
            className={cn("flex flex-col items-center gap-1 p-2 transition-colors", mainTab === 'alerts' ? "text-indigo-600" : "text-gray-400 hover:text-gray-600")}
          >
            <div className="relative">
              <Bell className={cn("w-6 h-6", mainTab === 'alerts' && "fill-indigo-600/10")} />
              {allowNotifications && <span className="absolute top-0.5 right-0.5 w-2 h-2 bg-rose-500 rounded-full border border-white"></span>}
            </div>
            <span className="text-[10px] font-bold">{t.alerts}</span>
          </button>
          <button 
            onClick={() => setMainTab('settings')}
            className={cn("flex flex-col items-center gap-1 p-2 transition-colors", mainTab === 'settings' ? "text-indigo-600" : "text-gray-400 hover:text-gray-600")}
          >
            <Settings className={cn("w-6 h-6", mainTab === 'settings' && "fill-indigo-600/10")} />
            <span className="text-[10px] font-bold">{t.settings}</span>
          </button>
        </nav>

        {/* AI Chat Overlay Modal */}
        {isChatOpen && (
          <div className="absolute inset-0 z-50 bg-gray-50 flex flex-col animate-in slide-in-from-bottom-full duration-300">
            {/* Chat Header */}
            <div className="bg-white px-4 py-3 border-b border-gray-100 flex items-center gap-3 shrink-0 pt-6 shadow-sm">
              <button 
                onClick={() => setIsChatOpen(false)}
                className="p-2 -ml-2 rounded-full hover:bg-gray-50 text-gray-500 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex items-center gap-2 flex-1">
                <div className="p-1.5 bg-indigo-100 rounded-full">
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                </div>
                <div className="flex flex-col">
                  <span className="font-bold text-gray-900 text-sm leading-none">{t.chatTitle}</span>
                  <span className="text-[10px] text-green-500 font-medium mt-1">● Online</span>
                </div>
              </div>
            </div>

            {/* Chat Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 hide-scrollbar" ref={chatScrollRef}>
              {chatMessages.length === 0 && (
                <div className="text-center text-gray-400 text-xs my-auto">
                  {t.chatEmptyMsg}
                </div>
              )}
              {chatMessages.map(msg => (
                <div key={msg.id} className={cn("flex gap-2 max-w-[85%]", msg.sender === 'user' ? "self-end flex-row-reverse" : "self-start")}>
                  {msg.sender === 'ai' && (
                    <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center shrink-0 mt-1">
                      <Sparkles className="w-3 h-3 text-indigo-600" />
                    </div>
                  )}
                  <div className={cn(
                    "flex flex-col gap-2",
                    msg.sender === 'user' ? "items-end" : "items-start"
                  )}>
                    <div className={cn(
                      "px-3.5 py-2.5 text-sm",
                      msg.sender === 'user' 
                        ? "bg-indigo-600 text-white rounded-2xl rounded-tr-sm shadow-sm" 
                        : "bg-white border border-indigo-100/50 text-gray-800 rounded-2xl rounded-tl-sm shadow-sm"
                    )}>
                      {msg.text}
                    </div>
                    {/* Render Recommended Dish if any */}
                    {msg.sender === 'ai' && msg.recommendedDishId && (
                      <div className="w-full max-w-[260px]">
                        {(() => {
                          const item = menuItems.find(i => i.id === msg.recommendedDishId);
                          return item ? (
                            <MenuItemCard 
                              item={item} 
                              lang={lang} 
                              isFav={favorites.includes(item.id)} 
                              onToggleFav={toggleFavorite}
                              compact={true}
                            />
                          ) : null;
                        })()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Chat Input Area */}
            <div className="bg-white border-t border-gray-100 p-4 pb-8 shrink-0 shadow-[0_-10px_40px_-15px_rgba(0,0,0,0.05)]">
              <div className="relative flex items-center">
                <input 
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                  placeholder={t.chatPlaceholder}
                  className="w-full bg-gray-50 border border-gray-200 rounded-full pl-4 pr-12 py-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                />
                <button 
                  onClick={handleSendChat}
                  disabled={!chatInput.trim()}
                  className="absolute right-1.5 p-2 bg-indigo-600 text-white rounded-full disabled:bg-gray-300 disabled:text-gray-100 transition-colors"
                >
                  <Send className="w-4 h-4 -ml-0.5 mt-0.5" />
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
      
      {/* Global styles to hide scrollbar */}
      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .hide-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}} />
    </div>
  );
}
