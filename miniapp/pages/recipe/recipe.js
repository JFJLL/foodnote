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
  },

  deleteRecipe() {
    wx.showModal({
      title: "删除菜谱",
      content: "会从菜谱库、今日菜单和未确认周计划中移除，历史菜单记录会保留。",
      confirmText: "删除",
      confirmColor: "#d94e38",
      success: async (result) => {
        if (!result.confirm) return;
        try {
          await api.deleteRecipe(this.data.id);
          wx.showToast({ title: "已删除", icon: "success" });
          wx.navigateBack();
        } catch (error) {
          wx.showToast({ title: error.message || "删除失败", icon: "none" });
        }
      }
    });
  }
});
