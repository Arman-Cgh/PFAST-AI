class ContextOptimizer:


    @staticmethod
    def clean_text(value):

        if value is None:
            return ""

        return str(value).strip()



    @staticmethod
    def clean_dict(data):

        if not isinstance(data, dict):
            return {}

        result = {}

        for key, value in data.items():

            if value is None:
                continue


            if isinstance(value, str):

                value = value.strip()

                if not value:
                    continue


            result[key] = value


        return result



    @staticmethod
    def optimize(
        context,
        intent="chat"
    ):


        if not isinstance(context, dict):

            return {}



        profile = ContextOptimizer.clean_dict(
            context.get("profile")
        )


        memory = context.get(
            "memory",
            {}
        )


        if not isinstance(memory, dict):

            memory = {}

        else:

            memory = ContextOptimizer.clean_dict(
                memory
            )



        state = ContextOptimizer.clean_dict(
            context.get("state")
        )



        project = context.get(
            "project",
            ""
        )



        history = context.get(
            "history",
            []
        )



        if not isinstance(history, list):

            history = []



        clean_history = []



        for item in history:


            if not isinstance(item, dict):

                continue


            content = ContextOptimizer.clean_text(
                item.get("content")
            )


            if not content:

                continue



            clean_history.append(
                {
                    "role": item.get(
                        "role",
                        "user"
                    ),

                    "content": content
                }
            )



        if intent == "code":

            return {

                "profile": {},

                "memory": {
                    key:value
                    for key,value in memory.items()
                    if key in (
                        "active_project",
                        "current_goal",
                        "preferences"
                    )
                },

                "history": clean_history[-3:],

                "state": state,

                "project": project
            }



        if intent == "memory":

            return {

                "profile": profile,

                "memory": memory,

                "history": [],

                "state": state,

                "project": project
            }



        if intent == "task":

            return {

                "profile": {},

                "memory": {},

                "history": clean_history[-2:],

                "state": state,

                "project": ""
            }



        return {

            "profile": profile,

            "memory": memory,

            "history": clean_history[-8:],

            "state": state,

            "project": project
        }