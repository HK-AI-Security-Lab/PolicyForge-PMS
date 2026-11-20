// policy-version: pathguard-demo/2

@id("host-create-weather-task")
permit (
  principal == Agent::"host-agent",
  action == Action::"task:create",
  resource == TaskType::"weather"
);

@id("host-close-weather-task")
permit (
  principal == Agent::"host-agent",
  action == Action::"task:close",
  resource == TaskType::"weather"
);

@id("host-create-stay-task")
permit (
  principal == Agent::"host-agent",
  action == Action::"task:create",
  resource == TaskType::"stay"
);

@id("host-close-stay-task")
permit (
  principal == Agent::"host-agent",
  action == Action::"task:close",
  resource == TaskType::"stay"
);

@id("host-weather-send")
permit (
  principal == Agent::"host-agent",
  action == Action::"a2a:message:send",
  resource == Agent::"weather-agent"
) when {
  context.task_type == "weather"
};

@id("host-weather-read")
permit (
  principal == Agent::"host-agent",
  action == Action::"a2a:tasks:get",
  resource == Agent::"weather-agent"
) when {
  context.task_type == "weather"
};

@id("host-stay-send")
permit (
  principal == Agent::"host-agent",
  action == Action::"a2a:message:send",
  resource == Agent::"airbnb-agent"
) when {
  context.task_type == "stay"
};

@id("host-stay-read")
permit (
  principal == Agent::"host-agent",
  action == Action::"a2a:tasks:get",
  resource == Agent::"airbnb-agent"
) when {
  context.task_type == "stay"
};

@id("weather-discover")
permit (
  principal == Agent::"weather-agent",
  action == Action::"mcp:discover",
  resource == Tool::"weather-mcp"
);

@id("weather-call")
permit (
  principal == Agent::"weather-agent",
  action == Action::"mcp:tools:call",
  resource == Tool::"weather-mcp"
) when {
  context.task_type == "weather"
};

@id("airbnb-discover")
permit (
  principal == Agent::"airbnb-agent",
  action == Action::"mcp:discover",
  resource == Tool::"airbnb-mcp"
);

@id("airbnb-call")
permit (
  principal == Agent::"airbnb-agent",
  action == Action::"mcp:tools:call",
  resource == Tool::"airbnb-mcp"
) when {
  context.task_type == "stay"
};
