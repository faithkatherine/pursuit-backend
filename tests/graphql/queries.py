# ─── INSIGHTS / HOME ─────────────────────────────────────────────────────────

GET_HOME = """
query GetHome($offset: Int, $limit: Int, $timeFilter: String) {
  getHome(offset: $offset, limit: $limit, timeFilter: $timeFilter) {
    id
    greeting
    greetingPrompt
    timeOfDay
    dayOfWeek
    cityName
    weather {
      city
      condition
      temperature
      icon
    }
    userLocation
    allowLocationSharing
  }
}
"""

# ─── EVENTS ──────────────────────────────────────────────────────────────────

GET_EVENTS = """
query GetEvents($offset: Int, $limit: Int, $category: [ID]) {
  events(offset: $offset, limit: $limit, category: $category) {
    ok
    events {
      id
      name
      description
      date
      locationName
      coordinates
      isActive
      isFree
      category {
        id
        name
      }
    }
  }
}
"""

GET_EVENT = """
query GetEvent($id: ID!) {
  event(id: $id) {
    id
    name
    description
    date
    locationName
    isActive
    isFree
  }
}
"""

GET_SAVED_EVENTS = """
query GetSavedEvents($offset: Int, $limit: Int) {
  savedEvents(offset: $offset, limit: $limit) {
    ok
    events {
      id
      name
    }
  }
}
"""

# ─── CORE ────────────────────────────────────────────────────────────────────

GET_CATEGORIES = """
query GetCategories {
  getCategories {
    ok
    categories {
      id
      name
      icon
    }
  }
}
"""
