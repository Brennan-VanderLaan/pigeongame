Shader "Custom/ProceduralCheckerboard"
{
    Properties
    {
        _Color1 ("Color 1", Color) = (1, 1, 1, 1)
        _Color2 ("Color 2", Color) = (0.8, 0.8, 0.8, 1)
        _GridSize ("Grid Size", Float) = 1.0
        _GridLineColor ("Grid Line Color", Color) = (0, 0, 0, 1)
        _GridLineWidth ("Grid Line Width", Range(0.0, 0.2)) = 0.02
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

            float4 _Color1;
            float4 _Color2;
            float4 _GridLineColor;
            float _GridSize;
            float _GridLineWidth;
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
                // Use world position for consistent pattern
                float2 pos = i.worldPos.xz / _GridSize;

                // Calculate distance fade
                float distToCamera = length(i.worldPos - _WorldSpaceCameraPos);
                float fadeFactor = 1.0 - saturate((distToCamera - _FadeStart) / (_FadeEnd - _FadeStart));

                // Create checkerboard pattern with anti-aliasing
                float2 derivative = fwidth(pos);
                float2 checker = floor(pos);

                // Smooth checkerboard transition at edges to reduce aliasing
                float2 smoothChecker = smoothstep(0.48, 0.52, frac(pos));
                float pattern = fmod(checker.x + checker.y, 2.0);

                // Blend between patterns based on distance to reduce aliasing
                float blendFactor = saturate(length(derivative) * 2.0);
                pattern = lerp(pattern, 0.5, blendFactor);

                // Optional grid lines with anti-aliasing
                float2 grid = abs(frac(pos) - 0.5) / derivative;
                float gridDist = min(grid.x, grid.y);
                float gridLine = 1.0 - smoothstep(_GridLineWidth * 0.5, _GridLineWidth * 2.0, gridDist);
                gridLine *= fadeFactor;

                // Blend colors
                fixed4 color = lerp(_Color1, _Color2, pattern);
                color = lerp(color, _GridLineColor, gridLine);

                // Fade to average color at distance
                color = lerp((_Color1 + _Color2) * 0.5, color, fadeFactor);

                return color;
            }
            ENDCG
        }
    }
}
