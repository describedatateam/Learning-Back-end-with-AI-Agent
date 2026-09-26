from datetime import date

from rest_framework import serializers


class TaskSerializer(serializers.Serializer):
    # The tests call TaskSerializer(data={...}), then .is_valid(), then check .errors.
    title = serializers.CharField(max_length=200)
    # TODO 1: priority: a ChoiceField with choices "low", "medium", "high" and default="medium"
    # TODO 2: due_date: a DateField that may be left out (required=False) or None (allow_null=True)

    # TODO 3: def validate_title(self, value): fewer than 3 characters ->
    #         raise serializers.ValidationError("Title must be at least 3 characters.")
    # TODO 4: def validate_due_date(self, value): not None and before date.today() ->
    #         raise serializers.ValidationError("Due date cannot be in the past.")

    # TODO 5: def validate(self, attrs): priority "high" with no due_date ->
    #         raise serializers.ValidationError({"due_date": "High priority tasks need a due date."})
    #         Remember to return value / return attrs when everything is fine.
