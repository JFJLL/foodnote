const api = require("../../utils/api");

Page({
  data: {
    recipes: [],
    menuCount: 0,
    preferences: null,
    recipeQuery: "",
    recipePlatform: "",
    platformOptions: ["全部平台", "小红书", "抖音"],
    platformIndex: 0,
    loading: true,
    error: ""
  },

  onShow() {
    this.load();
  },

  async load() {
    this.setData({ loading: true, error: "" });
    try {
      const [recipes, menu, preferences] = await Promise.all([
        api.listRecipes(this.data.recipeQuery, this.data.recipePlatform),
        api.listMenu(),
        api.getPreferences()
      ]);
      this.setData({ recipes, menuCount: menu.length, preferences, loading: false });
    } catch (error) {
      this.setData({ error: error.message || "加载失败", loading: false });
    }
  },

  openRecipe(event) {
    wx.navigateTo({ url: `/pages/recipe/recipe?id=${event.currentTarget.dataset.id}` });
  },

  async addRecipe(event) {
    try {
      await api.addMenuItem(event.currentTarget.dataset.id, this.data.preferences ? this.data.preferences.default_servings : 1);
      wx.showToast({ title: "已加入菜单", icon: "success" });
      this.load();
    } catch (error) {
      wx.showToast({ title: error.message || "加入失败", icon: "none" });
    }
  },

  async randomRecipe() {
    try {
      const recipes = await api.randomRecipes(1);
      if (recipes.length) {
        wx.navigateTo({ url: `/pages/recipe/recipe?id=${recipes[0].id}` });
      }
    } catch (error) {
      wx.showToast({ title: error.message || "随机失败", icon: "none" });
    }
  },

  updateRecipeQuery(event) {
    this.setData({ recipeQuery: event.detail.value });
  },

  updateRecipePlatform(event) {
    const platforms = ["", "xiaohongshu", "douyin"];
    const index = Number(event.detail.value);
    this.setData({ recipePlatform: platforms[index] || "", platformIndex: index });
    this.load();
  },

  searchRecipes() {
    this.load();
  }
});
