from datetime import date

from rest_framework import serializers


class TaskSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    priority = serializers.ChoiceField(choices=["low", "medium", "high"], default="medium")
    due_date = serializers.DateField(required=False, allow_null=True)

    def validate_title(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        return value

    def validate_due_date(self, value):
        if value is not None and value < date.today():
            raise serializers.ValidationError("Due date cannot be in the past.")
        return value

    def validate(self, attrs):
        if attrs.get("priority") == "high" and not attrs.get("due_date"):
            raise serializers.ValidationError({"due_date": "High priority tasks need a due date."})
        return attrs
