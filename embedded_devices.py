data = {
  "gadgets": [
    {
      "id": "light_living",
      "type": "light",
      "room": "living",
      "position": [
        180,
        160
      ],
      "size": [
        50,
        50
      ],
      "state": 0,
      "color_modes": [
        "off",
        "warm_white",
        "bright_yellow",
        "cool_blue"
      ]
    },
    {
      "id": "ac_living",
      "type": "ac",
      "room": "living",
      "position": [
        600,
        160
      ],
      "size": [
        60,
        60
      ],
      "on": True,
      "temperature": 20,
      "range": [
        18,
        28
      ]
    },
    {
      "id": "tv_living",
      "type": "tv",
      "room": "living",
      "position": [
        350,
        380
      ],
      "size": [
        100,
        60
      ],
      "channel": 4,
      "channels": [
        {
          "id": 0,
          "name": "Off",
          "color": "gray"
        },
        {
          "id": 1,
          "name": "News",
          "color": "blue"
        },
        {
          "id": 2,
          "name": "Cartoon",
          "color": "green"
        },
        {
          "id": 3,
          "name": "Sports",
          "color": "red"
        },
        {
          "id": 4,
          "name": "Movies",
          "color": "purple"
        }
      ]
    },
    {
      "id": "light_bedroom",
      "type": "light",
      "room": "bedroom",
      "position": [
        180,
        460
      ],
      "size": [
        50,
        50
      ],
      "state": 1,
      "color_modes": [
        "off",
        "warm_white",
        "bright_yellow",
        "cool_blue"
      ]
    },
    {
      "id": "door_bedroom",
      "type": "door_lock",
      "room": "bedroom",
      "position": [
        700,
        460
      ],
      "size": [
        60,
        60
      ],
      "locked": True
    }
  ],
  "rooms": [
    {
      "name": "living",
      "area": [
        100,
        100,
        700,
        300
      ]
    },
    {
      "name": "bedroom",
      "area": [
        100,
        400,
        700,
        150
      ]
    }
  ]
}