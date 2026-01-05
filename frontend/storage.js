// Storage layer - easy to swap out for Supabase later
class Storage {
    constructor() {
        this.userId = this.getUserId();
    }

    // Get or create user ID
    getUserId() {
        let userId = localStorage.getItem('lifestats_userId');
        if (!userId) {
            userId = 'user-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('lifestats_userId', userId);
        }
        return userId;
    }

    // Save a meal
    saveMeal(foodName, mealType, nutrition = null) {
        const meals = this.getMeals();
        const newMeal = {
            id: 'meal-' + Date.now(),
            userId: this.userId,
            foodName: foodName,
            mealType: mealType,
            nutrition: nutrition || { calories: 0, protein: 0, carbs: 0, fat: 0 },
            timestamp: Date.now()
        };
        meals.push(newMeal);
        localStorage.setItem('lifestats_meals', JSON.stringify(meals));
        return newMeal;
    }

    // Get all meals
    getMeals() {
        const mealsJson = localStorage.getItem('lifestats_meals');
        return mealsJson ? JSON.parse(mealsJson) : [];
    }

    // Get meals for today
    getTodaysMeals() {
        const meals = this.getMeals();
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        return meals.filter(meal => {
            const mealDate = new Date(meal.timestamp);
            mealDate.setHours(0, 0, 0, 0);
            return mealDate.getTime() === today.getTime();
        });
    }

    // Delete a meal
    deleteMeal(mealId) {
        const meals = this.getMeals();
        const filtered = meals.filter(meal => meal.id !== mealId);
        localStorage.setItem('lifestats_meals', JSON.stringify(filtered));
    }

    // Get meals grouped by date
    getMealsByDate() {
        const meals = this.getMeals();
        const grouped = {};

        meals.forEach(meal => {
            const date = new Date(meal.timestamp);
            const dateKey = date.toLocaleDateString();

            if (!grouped[dateKey]) {
                grouped[dateKey] = [];
            }
            grouped[dateKey].push(meal);
        });

        return grouped;
    }
}

// Export for use in HTML
const storage = new Storage();
