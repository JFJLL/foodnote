const api = require("../../utils/api");

Page({
  data: {
    id: "",
    recipe: null,
    preferences: null,
    loading: true,
    error: ""
  },

  onLoad(query) {
    this.setData({ id: query.id });
    this.load(query.id);
  },

  async load(id) {
    this.setData({ loading: true, error: "" });
    try {
      const [recipe, preferences] = await Promise.all([api.getRecipe(id), api.getPreferences()]);
      this.setData({ recipe, preferences, loading: false });
    } catch (error) {
      this.setData({ error: error.message || "加载失败", loading: false });
    }
  },

  async addToMenu() {
    try {
      await api.addMenuItem(this.data.id, this.data.preferences ? this.data.preferences.default_servings : 1);
      wx.showToast({ title: "已加入菜单", icon: "success" });
    } catch (error) {
      wx.showToast({ title: error.message || "加入失败", icon: "none" });
    }
  },

  copySource() {
    wx.setClipboardData({ data: this.data.recipe.source_url });
  }
});
