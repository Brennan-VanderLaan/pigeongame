Shader "Custom/ProceduralGrid"
{
    Properties
    {
        _GridColor ("Grid Color", Color) = (0, 0, 0, 1)
        _BackgroundColor ("Background Color", Color) = (1, 1, 1, 1)
        _GridSize ("Grid Size", Float) = 1.0
        _LineWidth ("Line Width", Range(0.01, 0.5)) = 0.05
        _MajorGridInterval ("Major Grid Interval", Int) = 5
        _MajorLineWidth ("Major Line Width", Range(0.01, 0.5)) = 0.1
        _MajorGridColor ("Major Grid Color", Color) = (0, 0, 0, 1)
        _FadeStart ("Fade Start Distance", Float) = 20.0
        _FadeEnd ("Fade End Distance", Float) = 50.0
    }

    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 100

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
                float3 worldPos : TEXCOORD1;
            };

            float4 _GridColor;
            float4 _BackgroundColor;
            float4 _MajorGridColor;
            float _GridSize;
            float _LineWidth;
            float _MajorLineWidth;
            int _MajorGridInterval;
            float _FadeStart;
            float _FadeEnd;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                // Use world position for consistent grid across all surfaces
                float2 pos = i.worldPos.xz / _GridSize;

                // Calculate distance fade to reduce aliasing at far distances
                float distToCamera = length(i.worldPos - _WorldSpaceCameraPos);
                float fadeFactor = 1.0 - saturate((distToCamera - _FadeStart) / (_FadeEnd - _FadeStart));

                // Improve anti-aliasing by using derivative-based filtering
                float2 derivative = fwidth(pos);
                float2 grid = abs(frac(pos - 0.5) - 0.5) / derivative;
                float gridDist = min(grid.x, grid.y);

                // Calculate major grid lines
                float2 majorPos = i.worldPos.xz / (_GridSize * _MajorGridInterval);
                float2 majorDerivative = fwidth(majorPos);
                float2 majorGrid = abs(frac(majorPos - 0.5) - 0.5) / majorDerivative;
                float majorGridDist = min(majorGrid.x, majorGrid.y);

                // Anti-aliased lines with improved smoothstep range
                float lineThickness = max(_LineWidth, derivative.x + derivative.y);
                float majorLineThickness = max(_MajorLineWidth, majorDerivative.x + majorDerivative.y);

                float minorGridMask = 1.0 - smoothstep(0.0, lineThickness * 2.0, gridDist);
                float majorGridMask = 1.0 - smoothstep(0.0, majorLineThickness * 2.0, majorGridDist);

                // Apply distance fade
                minorGridMask *= fadeFactor;
                majorGridMask *= fadeFactor;

                // Blend colors
                fixed4 color = _BackgroundColor;
                color = lerp(color, _GridColor, minorGridMask);
                color = lerp(color, _MajorGridColor, majorGridMask);

                return color;
            }
            ENDCG
        }
    }
}
