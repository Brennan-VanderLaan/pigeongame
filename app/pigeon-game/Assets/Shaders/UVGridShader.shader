Shader "Custom/UVGrid"
{
    Properties
    {
        _GridColor ("Grid Color", Color) = (0, 1, 0, 1)
        _BackgroundColor ("Background Color", Color) = (0.2, 0.2, 0.2, 1)
        _GridDensity ("Grid Density", Float) = 10.0
        _LineWidth ("Line Width", Range(0.01, 0.5)) = 0.05
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
            };

            float4 _GridColor;
            float4 _BackgroundColor;
            float _GridDensity;
            float _LineWidth;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                // UV-based grid (useful for checking UV mapping)
                float2 pos = i.uv * _GridDensity;

                // Improved anti-aliasing with derivative-based filtering
                float2 derivative = fwidth(pos);
                float2 grid = abs(frac(pos - 0.5) - 0.5) / derivative;
                float gridDist = min(grid.x, grid.y);

                // Anti-aliased lines with adaptive thickness
                float lineThickness = max(_LineWidth, derivative.x + derivative.y);
                float gridMask = 1.0 - smoothstep(0.0, lineThickness * 2.0, gridDist);

                // Show UV coordinates with color gradient at borders
                float uvBorderX = smoothstep(0.0, 0.1, i.uv.x) * (1.0 - smoothstep(0.9, 1.0, i.uv.x));
                float uvBorderY = smoothstep(0.0, 0.1, i.uv.y) * (1.0 - smoothstep(0.9, 1.0, i.uv.y));

                // Red channel = U, Green channel = V
                fixed4 uvColor = fixed4(i.uv.x, i.uv.y, 0, 1);

                // Blend colors
                fixed4 color = lerp(_BackgroundColor, uvColor * 0.3, uvBorderX * uvBorderY);
                color = lerp(color, _GridColor, gridMask);

                return color;
            }
            ENDCG
        }
    }
}
