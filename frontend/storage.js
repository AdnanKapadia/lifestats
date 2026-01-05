// Storage layer - Communicates with Backend API
class Storage {
    constructor() {
        this.userId = this.getUserId();
    }

    // Get or create user ID (Persist in LocalStorage still for identity)
    getUserId() {
        let userId = localStorage.getItem('lifestats_userId');
        if (!userId) {
            userId = 'user-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('lifestats_userId', userId);
        }
        return userId;
    }

    // Save a meal (Async)
    async saveMeal(foodName, mealType, nutrition = null) {
        const newMeal = {
            id: 'meal-' + Date.now(),
            userId: this.userId,
            foodName: foodName,
            mealType: mealType,
            nutrition: nutrition || { calories: 0, protein: 0, carbs: 0, fat: 0 },
            timestamp: Date.now()
        };

        try {
            const response = await fetch('/api/meals', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(newMeal)
            });

            if (!response.ok) {
                throw new Error('Failed to save meal');
            }
            return await response.json();
        } catch (error) {
            console.error('Error saving meal:', error);
            // Fallback? Or just alert. For now, alert.
            alert('Error saving meal. Check connection.');
            return null;
        }
    }

    // Get meals (Async)
    async getMeals() {
        try {
            const response = await fetch(`/api/meals?userId=${this.userId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch meals');
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching meals:', error);
            return [];
        }
    }

    // Get meals for today (Async) - Efficient filtering happens in JS for now, simpler
    async getTodaysMeals() {
        const meals = await this.getMeals();
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        return meals.filter(meal => {
            const mealDate = new Date(meal.timestamp);
            mealDate.setHours(0, 0, 0, 0);
            return mealDate.getTime() === today.getTime();
        });
    }

    // Delete a meal (Async)
    async deleteMeal(mealId) {
        try {
            const response = await fetch(`/api/meals/${mealId}?userId=${this.userId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                throw new Error('Failed to delete meal');
            }
            return true;
        } catch (error) {
            console.error('Error deleting meal:', error);
            return false;
        }
    }
}

// Export for use in HTML
const storage = new Storage();
