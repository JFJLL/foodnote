const app = getApp();

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBase}${path}`,
      method: options.method || "GET",
      data: options.data,
      header: {
        "content-type": "application/json"
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject(new Error(res.data && res.data.detail ? res.data.detail : `请求失败：${res.statusCode}`));
        }
      },
      fail(error) {
        reject(error);
      }
    });
  });
}

function mediaUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const normalized = path.replace(/\\/g, "/");
  const storageIndex = normalized.lastIndexOf("/storage/");
  if (storageIndex >= 0) {
    return `${app.globalData.apiBase}${normalized.slice(storageIndex)}`;
  }
  return "";
}

function normalizeRecipe(recipe) {
  return {
    ...recipe,
    steps: (recipe.steps || []).map((step, index) => ({
      ...step,
      display_index: index + 1,
      display_title: step.title || "步骤"
    })),
    cover_url: mediaUrl(recipe.cover_path),
    tag_text: (recipe.tags || []).join(" / "),
    display_description: recipe.description || "打开查看制作步骤"
  };
}

function normalizeMenuItem(item) {
  return {
    ...item,
    recipe: normalizeRecipe(item.recipe)
  };
}

function normalizeMenuOrder(order) {
  return {
    ...order,
    summary: (order.items || []).map((item) => `${item.recipe_title} x${item.servings}`).join(" / ")
  };
}

function normalizeWeeklyPlan(plan) {
  return {
    ...plan,
    items: (plan.items || []).map((item) => ({
      ...item,
      recipe: normalizeRecipe(item.recipe),
      display_label: `${item.date} ${item.meal_label}`
    }))
  };
}

module.exports = {
  async listRecipes() {
    const recipes = await request("/api/recipes");
    return recipes.map(normalizeRecipe);
  },
  async randomRecipes(count) {
    const recipes = await request(`/api/recipes/random?count=${count || 1}`);
    return recipes.map(normalizeRecipe);
  },
  getPreferences() {
    return request("/api/preferences");
  },
  updatePreferences(preferences) {
    return request("/api/preferences", {
      method: "PATCH",
      data: preferences
    });
  },
  async getRecipe(id) {
    const recipe = await request(`/api/recipes/${id}`);
    return normalizeRecipe(recipe);
  },
  async listMenu() {
    const items = await request("/api/today-menu/items");
    return items.map(normalizeMenuItem);
  },
  shoppingList() {
    return request("/api/today-menu/shopping-list").then((items) =>
      items.map((item) => ({
        ...item,
        amount_display: item.amount || `x${item.servings_total}`
      }))
    );
  },
  listMenuOrders(query) {
    const suffix = query ? `?query=${encodeURIComponent(query)}` : "";
    return request(`/api/menu-orders${suffix}`).then((orders) => orders.map(normalizeMenuOrder));
  },
  cookingStats(limit) {
    return request(`/api/cooking-stats?limit=${limit || 8}`);
  },
  listWeeklyPlans(limit) {
    return request(`/api/weekly-plans?limit=${limit || 1}`).then((plans) => plans.map(normalizeWeeklyPlan));
  },
  createWeeklyPlan(payload) {
    return request("/api/weekly-plans", {
      method: "POST",
      data: payload || {}
    }).then(normalizeWeeklyPlan);
  },
  addWeeklyPlanItemToToday(itemId) {
    return request(`/api/weekly-plans/items/${itemId}/add-to-today`, { method: "POST" }).then(normalizeMenuItem);
  },
  createMenuOrder(title, note) {
    return request("/api/menu-orders", {
      method: "POST",
      data: { title: title || "今日菜单", note: note || "" }
    }).then(normalizeMenuOrder);
  },
  restoreMenuOrder(orderId) {
    return request(`/api/menu-orders/${orderId}/restore`, { method: "POST" }).then((items) => items.map(normalizeMenuItem));
  },
  addMenuItem(recipeId, servings, note) {
    return request("/api/today-menu/items", {
      method: "POST",
      data: { recipe_id: recipeId, servings: servings || 1, note: note || "" }
    });
  },
  updateMenuItem(itemId, payload) {
    return request(`/api/today-menu/items/${itemId}`, {
      method: "PATCH",
      data: payload
    }).then(normalizeMenuItem);
  },
  removeMenuItem(itemId) {
    return request(`/api/today-menu/items/${itemId}`, { method: "DELETE" });
  },
  clearMenu() {
    return request("/api/today-menu/items", { method: "DELETE" });
  }
};
