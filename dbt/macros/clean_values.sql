{% macro clean_string(column) -%}
nullif(trim({{ column }}), '')
{%- endmacro %}

{% macro clean_boolean(column) -%}
case lower(trim({{ column }}))
    when '1' then true
    when 'true' then true
    when 'yes' then true
    when '0' then false
    when 'false' then false
    when 'no' then false
    else null
end
{%- endmacro %}
