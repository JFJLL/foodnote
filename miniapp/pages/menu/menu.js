const api = require("../../utils/api");

Page({
  data: {
    items: [],
    shoppingList: [],
    orders: [],
    cookingStats: [],
    weeklyPlan: null,
    orderQuery: "",
    preferences: null,
    preferredTagsText: "",
    blockedTagsText: "",
    dislikedIngredientsText: "",
    loading: true,
    error: ""
  },

  onShow() {
    this.load();
  },

  async load() {
    this.setData({ loading: true, error: "" });
    try {
      const [items, shoppingList, orders, cookingStats, weeklyPlans, preferences] = await Promise.all([
        api.listMenu(),
        api.shoppingList(),
        api.listMenuOrders(this.data.orderQuery),
        api.cookingStats(8),
        api.listWeeklyPlans(1),
        api.getPreferences()
      ]);
      this.setData({
        items: items.map((item, index) => ({ ...item, display_index: index + 1 })),
        shoppingList,
        orders,
        cookingStats,
        weeklyPlan: weeklyPlans[0] || null,
        preferences,
        preferredTagsText: (preferences.preferred_tags || []).join("，"),
        blockedTagsText: (preferences.blocked_tags || []).join("，"),
        dislikedIngredientsText: (preferences.disliked_ingredients || []).join("，"),
        loading: false
      });
    } catch (error) {
      this.setData({ error: error.message || "加载失败", loading: false });
    }
  },

  async removeItem(event) {
    try {
      await api.removeMenuItem(event.currentTarget.dataset.id);
      this.load();
    } catch (error) {
      wx.showToast({ title: error.message || "移除失败", icon: "none" });
    }
  },

  async decreaseServings(event) {
    const item = this.data.items.find((entry) => entry.id === event.currentTarget.dataset.id);
    if (!item) return;
    await this.updateItem(item.id, { servings: Math.max(1, item.servings - 1) });
  },

  async increaseServings(event) {
    const item = this.data.items.find((entry) => entry.id === event.currentTarget.dataset.id);
    if (!item) return;
    await this.updateItem(item.id, { servings: Math.min(20, item.servings + 1) });
  },

  async updateNote(event) {
    await this.updateItem(event.currentTarget.dataset.id, { note: event.detail.value });
  },

  async updateItem(id, payload) {
    try {
      await api.updateMenuItem(id, payload);
      this.load();
    } catch (error) {
      wx.showToast({ title: error.message || "更新失败", icon: "none" });
    }
  },

  async clearMenu() {
    try {
      await api.clearMenu();
      this.load();
    } catch (error) {
      wx.showToast({ title: error.message || "清空失败", icon: "none" });
    }
  },

  async confirmMenu() {
    try {
      const order = await api.createMenuOrder("今日菜单", "");
      wx.showToast({ title: `已确认${order.item_count}道`, icon: "success" });
      this.load();
    } catch (error) {
      wx.showToast({ title: error.message || "确认失败", icon: "none" });
    }
  },

  async restoreOrder(event) {
    try {
      const items = await api.restoreMenuOrder(event.currentTarget.dataset.id);
      wx.showToast({ title: `已复用${items.length}道`, icon: "success" });
      this.load();
    } catch (error) {
      wx.showToast({ title: error.message || "复用失败", icon: "none" });
    }
  },

  async generateWeeklyPlan() {
    try {
      const plan = await api.createWeeklyPlan({
        days: 7,
        meals_per_day: 2,
        servings: this.data.preferences ? this.data.preferences.default_servings : 1
      });
      this.setData({ weeklyPlan: plan });
      wx.showToast({ title: "已生成本周菜单", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.message || "生成失败", icon: "none" });
    }
  },

  async addWeeklyPlanItem(event) {
    try {
      await api.addWeeklyPlanItemToToday(event.currentTarget.dataset.id);
      wx.showToast({ title: "已加入今日菜单", icon: "success" });
      this.load();
    } catch (error) {
      wx.showToast({ title: error.message || "加入失败", icon: "none" });
    }
  },

  updateOrderQuery(event) {
    this.setData({ orderQuery: event.detail.value });
  },

  async searchOrders() {
    try {
      const orders = await api.listMenuOrders(this.data.orderQuery);
      this.setData({ orders });
    } catch (error) {
      wx.showToast({ title: error.message || "搜索失败", icon: "none" });
    }
  },

  updatePreferredTags(event) {
    this.setData({ preferredTagsText: event.detail.value });
  },

  updateBlockedTags(event) {
    this.setData({ blockedTagsText: event.detail.value });
  },

  updateDislikedIngredients(event) {
    this.setData({ dislikedIngredientsText: event.detail.value });
  },

  updateDefaultServings(event) {
    this.setData({ "preferences.default_servings": clamp(Number(event.detail.value), 1, 20) });
  },

  updateAvoidRecentDays(event) {
    this.setData({ "preferences.avoid_recent_days": clamp(Number(event.detail.value), 0, 365) });
  },

  async savePreferences() {
    if (!this.data.preferences) return;
    try {
      const preferences = await api.updatePreferences({
        preferred_tags: splitList(this.data.preferredTagsText),
        blocked_tags: splitList(this.data.blockedTagsText),
        disliked_ingredients: splitList(this.data.dislikedIngredientsText),
        default_servings: this.data.preferences.default_servings,
        avoid_recent_days: this.data.preferences.avoid_recent_days
      });
      this.setData({ preferences });
      wx.showToast({ title: "偏好已保存", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.message || "保存失败", icon: "none" });
    }
  }
});

function splitList(value) {
  return String(value || "")
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function clamp(value, min, max) {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}
